"""The dashboard assistant: a bounded, server-side tool-calling loop.

This is the repo's one *agent loop* (CLAUDE.md rule 1, exception b). It is
fenced hard so it never becomes an inference engine:

  - The tools are read-only. Most are existing Aito-backed reads — the same
    functions MCP and the dashboard use, no new logic, no heuristics, no
    writes. Two exceptions read the *external* web for facts Aito can't hold:
    `web_search` (websearch.py) finds pages, `fetch_page` (webfetch.py) reads
    one. Both still narrate, never score; rule 2 keeps every internal number
    in Aito. web_search is off unless a key is configured; fetch_page is
    keyless but SSRF-guarded to public addresses and can be disabled by env.
  - The model picks *which* tool and narrates the result; it never computes a
    ranking, score, or prediction itself.
  - The loop is bounded (MAX_ROUNDS); a tool error is returned to the model
    as a tool result, never swallowed (rule 3).
  - The LLM (llm.py) and the search backend (websearch.py) are both swappable
    providers; a named provider with no key → loud failure.

The tools live in one registry (`TOOLS`) — the seam meant for tailoring. Each
`Tool` carries its name, schema, a uniform `run(ctx, args)`, an optional
`available(ctx)` predicate, and an optional system-prompt `note`. `run_turn`
filters the registry by availability and the COMPANY_AI_ASSISTANT_TOOLS
allowlist, so a fork can add, drop, or curate tools without touching the loop.

`run_turn` takes the conversation so far and returns the assistant's reply
plus a trace of the tool calls (the trace is what makes this double as an
MCP-contract tester — you see exactly which tool ran with which args).
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Callable

from . import clock
from . import (analytics, changelog, deals, decisions, experiments, funnels, queries,
               schema, scorer, search, todos)
from .aito import AitoClient
from .config import Config
from .llm import make_client
from .webfetch import make_fetcher
from .websearch import make_search_client

MAX_ROUNDS = 6  # hard bound on tool rounds per turn
# Reply budget per LLM call. Must be generous: on a *reasoning* model (gpt-5*,
# o*) the hidden reasoning tokens count against this budget. Too small and it is
# fully consumed by reasoning — the model returns finish_reason=length with
# EMPTY content (no answer), or, worse on a *complex* request, truncates the
# tool_call it was emitting mid-JSON, so the arguments no longer parse. 8192
# leaves room for reasoning + the tool call + a full answer; _dispatch_call
# still surfaces a truncated call gracefully if the budget is ever exceeded.
REPLY_TOKENS = 8192


@dataclass
class ToolContext:
    """What a tool needs to run: the Aito client, the as-of date, and the
    external web providers (None when unconfigured). One object so adding a
    tool never changes the dispatch signature."""
    aito: AitoClient
    as_of: date
    search: object | None = None
    fetch: object | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict                 # JSON schema for the function arguments
    run: Callable                    # (ctx: ToolContext, args: dict) -> JSON-able
    available: Callable | None = None  # (ctx) -> bool; None = always available
    note: str = ""                   # optional line appended to the system prompt

    def is_available(self, ctx: "ToolContext") -> bool:
        return self.available is None or self.available(ctx)


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props,
            "required": required or [], "additionalProperties": False}


# The whole tool surface as one registry — this is the seam meant for
# tailoring (e.g. a fork with different tools). To add a tool, append a Tool:
# give it a name, a schema, a `run(ctx, args)` that returns JSON-able data, and
# — if it needs something optional — an `available(ctx)` predicate and a `note`
# for the system prompt. `run_turn` filters by availability and the
# COMPANY_AI_ASSISTANT_TOOLS allowlist, so nothing else has to change.
#
# Most tools wrap one existing Aito-backed read; the predictive work is inside
# them (in Aito), never here (rule 2). The last two read the external web and
# gate on their provider being present (see websearch.py / webfetch.py).
def _web_search(ctx: "ToolContext", a: dict) -> dict:
    results = ctx.search.search(a["query"], count=a.get("count", 5))
    return {"query": a["query"], "results": [asdict(r) for r in results]}


def _fetch_page(ctx: "ToolContext", a: dict) -> dict:
    return asdict(ctx.fetch.fetch(a["url"]))


def _smart_search(ctx: "ToolContext", a: dict) -> dict:
    # serve() builds the index on first use and logs impressions server-side
    # (A+C telemetry on a read — not an assistant write; the assistant records
    # no clicks). The ranking is Aito's (search.py); the model only narrates
    # the hits (rule 2).
    # log=False: the assistant is read-only — it must not write impression
    # telemetry (a prompt-injected loop could otherwise spam the click-training
    # signal). The ranking is still Aito's; only the logging side effect is off.
    from . import embed as embed_mod
    return search.serve(ctx.aito, a["query"], kind=a.get("kind"),
                        top_n=a.get("top_n", 10), source="assistant", log=False,
                        embed=embed_mod.embedder(Config.from_env()))


WEB_SEARCH = "web_search"
FETCH_PAGE = "fetch_page"

TOOLS: list[Tool] = [
    Tool("who_to_call",
         "Today's call queue for a window, ranked by Aito's probability of a good outcome.",
         _obj({"window": {"type": "string", "enum": schema.call_windows()},
               "top_n": {"type": "integer"}}, ["window"]),
         lambda ctx, a: queries.who_to_call(ctx.aito, a["window"], top_n=a.get("top_n", 5), as_of=ctx.as_of).derived),
    Tool("opener_context",
         "Evidence to open a call with a contact: how statistically similar contacts responded.",
         _obj({"contact_id": {"type": "string"}}, ["contact_id"]),
         lambda ctx, a: queries.opener_context(ctx.aito, a["contact_id"]).derived),
    Tool("what_changed",
         "Yesterday's outcomes and open follow-ups due soon.",
         _obj({}), lambda ctx, a: queries.what_changed(ctx.aito, as_of=ctx.as_of).derived),
    Tool("smart_search",
         "Search across content — docs, contacts, deals — ranked by Aito "
         "text-match relevance. Use to find the right items to ground an answer, then "
         "read the source. Optionally restrict to one kind (doc/contact/deal).",
         _obj({"query": {"type": "string"},
               "kind": {"type": "string", "enum": ["doc", "contact", "deal"]},
               "top_n": {"type": "integer"}}, ["query"]),
         lambda ctx, a: _smart_search(ctx, a)),
    Tool("deal_pipeline",
         "The sales pipeline: open deals, weighted value, per-deal close-likelihood, stalled flags.",
         _obj({}), lambda ctx, a: deals.pipeline(ctx.aito, as_of=ctx.as_of).derived),
    Tool("experiment_board",
         "The Build-Measure-Learn board: validated-learning rate, running bets, P(validated) by effort.",
         _obj({}), lambda ctx, a: experiments.board(ctx.aito).derived),
    Tool("decision_scorecard",
         "The dogfood loop: how often the operator accepts the agent, and whether its confidence is trustworthy.",
         _obj({}), lambda ctx, a: decisions.scorecard(ctx.aito).derived),
    Tool("segment_360",
         "A 360 read for a contact segment slice (keys: segment, tier, ai_lifecycle, source).",
         _obj({"segment": {"type": "object", "additionalProperties": {"type": "string"}}}),
         lambda ctx, a: analytics.segment_360(ctx.aito, a.get("segment") or None).derived),
    Tool("funnel",
         "A predictive funnel (website acquisition or sales), optionally sliced.",
         _obj({"name": {"type": "string", "enum": list(funnels.FUNNELS)},
               "slice": {"type": "object", "additionalProperties": {"type": "string"}}}, ["name"]),
         lambda ctx, a: funnels.funnel(ctx.aito, a["name"], a.get("slice") or None).derived),
    Tool("score_post",
         "Score a draft post's win-likelihood on its channel and the levers that move it.",
         _obj({"channel": {"type": "string"}}, ["channel"]),
         lambda ctx, a: scorer.score(ctx.aito, a["channel"]).derived),
    Tool("todos_now",
         "The action-first Now view: the most urgent committed actions across all areas, with slip-risk.",
         _obj({}), lambda ctx, a: todos.now(ctx.aito, as_of=ctx.as_of).derived),
    Tool("todos_area",
         "Open todos for one area (" + ", ".join(schema.TODO_AREA_ORDER) + "), with slip-risk.",
         _obj({"area": {"type": "string", "enum": list(schema.TODO_AREA_ORDER)}}, ["area"]),
         lambda ctx, a: todos.pipeline(ctx.aito, a["area"], as_of=ctx.as_of).derived),
    Tool("recent_changes",
         "The change log — items created and updated across the system (a todo done, "
         "a deal won/lost), newest first. Optionally filter by "
         "entity kind (todo/deal/routine/…).",
         _obj({"limit": {"type": "integer"}, "entity": {"type": "string"}}),
         lambda ctx, a: changelog.recent(ctx.aito, limit=a.get("limit", 50),
                                         entity=a.get("entity") or None)),
    # the external web reads — non-Aito, gated on their provider being present
    Tool(WEB_SEARCH,
         ("Search the public web for current, external facts Aito does not "
          "hold — company news, market moves, a person's current role, anything "
          "outside the sales database. Returns ranked results (title, url, "
          "snippet); cite the urls. Never use it for internal pipeline numbers "
          "— those come only from the Aito-backed tools."),
         _obj({"query": {"type": "string"}, "count": {"type": "integer"}}, ["query"]),
         _web_search, available=lambda ctx: ctx.search is not None,
         note=(" You also have web_search for facts outside the pipeline "
               "(company news, markets, people); use it for external context "
               "only, cite the urls, and keep internal numbers coming from the "
               "Aito tools.")),
    Tool(FETCH_PAGE,
         ("Fetch one public web page by URL and return its title and readable "
          "text — to read a docs page, an article, a company site, or a "
          "promising web_search result. Public http(s) pages only. Summarize "
          "and cite what you read; internal numbers still come from Aito."),
         _obj({"url": {"type": "string"}}, ["url"]),
         _fetch_page, available=lambda ctx: ctx.fetch is not None,
         note=(" You can fetch_page(url) to read a specific page — a docs page, "
               "an article, a site the user names, or a web_search result; "
               "summarize and cite it.")),
]

SYSTEM = (
    "You are the assistant inside a one-person company's sales dashboard. Your "
    "intuition lives in Aito, reached only through the tools provided — you do "
    "not rank, score, predict, or invent numbers yourself. Call tools to get "
    "facts, then answer concisely and honestly. Every figure you state must "
    "come from a tool result; if the data is thin or weak, say so plainly "
    "rather than embellishing. Prefer one or two well-chosen tool calls. The "
    "probabilities Aito returns are reported as they are, even when low."
)


def active_tools(ctx: ToolContext, allow: list[str] | None = None) -> list[Tool]:
    """The tools available for this turn: those whose provider is present, then
    narrowed to `allow` (the COMPANY_AI_ASSISTANT_TOOLS allowlist) when given."""
    tools = [t for t in TOOLS if t.is_available(ctx)]
    if allow:
        names = set(allow)
        tools = [t for t in tools if t.name in names]
    return tools


def tool_specs(tools: list[Tool]) -> list[dict]:
    """The OpenAI function-calling `tools` array for a set of tools."""
    return [{"type": "function",
             "function": {"name": t.name, "description": t.description,
                          "parameters": t.parameters}}
            for t in tools]


def system_prompt(tools: list[Tool]) -> str:
    """The base prompt plus each active tool's note (so a tool that isn't
    available is never described to the model)."""
    return SYSTEM + "".join(t.note for t in tools)


@dataclass
class Turn:
    reply: str
    trace: list[dict] = field(default_factory=list)   # [{tool, args, ok, error?}]
    rounds: int = 0


def _run_tool(ctx: ToolContext, by_name: dict, name: str,
              args: dict) -> tuple[dict, dict]:
    """Execute one tool call by name against the active registry. Returns
    (result_for_model, trace_entry). An unknown tool (hallucinated, or gated
    off this turn) and any tool error are surfaced to the model as the result,
    never swallowed (rule 3)."""
    tool = by_name.get(name)
    if tool is None:
        result = {"error": f"unknown tool {name!r}"}
        return result, {"tool": name, "args": args, "ok": False, "error": result["error"]}
    try:
        result = tool.run(ctx, args)
        return result, {"tool": name, "args": args, "ok": True}
    except Exception as exc:  # surface, don't hide (rule 3); the model sees it
        result = {"error": f"{type(exc).__name__}: {exc}"}
        return result, {"tool": name, "args": args, "ok": False, "error": result["error"]}


def _dispatch_call(ctx: ToolContext, by_name: dict, call: dict) -> tuple[dict, dict, str]:
    """Parse and run ONE tool_call from the model, robustly. Returns
    (result_for_model, trace_entry, tool_call_id).

    A complex request makes the model emit bigger tool calls, which sometimes
    arrive with malformed or truncated JSON arguments (or a missing field). That
    used to crash the whole turn — the parse was outside any guard — so one bad
    call sank the entire request. Here a bad structure or unparseable arguments
    is surfaced to the model as a tool error (rule 3), so the loop continues and
    the model can correct itself, exactly like any other tool error."""
    fn = call.get("function") or {}
    name = fn.get("name") or "?"
    call_id = call.get("id") or ""
    raw = fn.get("arguments")
    try:
        args = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        args = None
    if not isinstance(args, dict):
        err = f"could not parse arguments for {name!r}: {str(raw)[:200]}"
        return ({"error": err},
                {"tool": name, "args": raw, "ok": False, "error": err}, call_id)
    result, entry = _run_tool(ctx, by_name, name, args)
    return result, entry, call_id


def run_turn(history: list[dict], *, client: AitoClient | None = None,
             llm=None, search="__default__", fetch="__default__",
             as_of: date | None = None) -> Turn:
    """Drive one assistant turn. `history` is [{role, content}] (user/assistant);
    the system prompt and tool wiring are added here. Bounded by MAX_ROUNDS.

    The tool set for the turn is `active_tools(ctx)` — the registry filtered by
    each tool's availability and the COMPANY_AI_ASSISTANT_TOOLS allowlist.
    `search` (websearch.py) and `fetch` (webfetch.py) are the external web
    providers; left at the default they are built from config (None when
    unconfigured, which drops their tools). Pass an explicit provider (or None)
    in tests."""
    config = Config.from_env()
    client = client or AitoClient(config.instance_url, config.api_key)
    llm = llm or make_client(config)
    if search == "__default__":
        search = make_search_client(config)
    if fetch == "__default__":
        fetch = make_fetcher(config)
    as_of = as_of or clock.today()

    ctx = ToolContext(aito=client, as_of=as_of, search=search, fetch=fetch)
    tools = active_tools(ctx, allow=config.assistant_tools or None)
    by_name = {t.name: t for t in tools}

    messages = [{"role": "system", "content": system_prompt(tools)}]
    for m in history:
        assert m.get("role") in ("user", "assistant"), f"bad message role {m.get('role')!r}"
        messages.append({"role": m["role"], "content": m["content"]})

    trace: list[dict] = []
    specs = tool_specs(tools)
    for rounds in range(1, MAX_ROUNDS + 1):
        msg = llm.chat(messages, tools=specs, max_tokens=REPLY_TOKENS)
        calls = msg.get("tool_calls") or []
        if not calls:
            return Turn(reply=msg.get("content") or "(the assistant returned an empty reply)",
                        trace=trace, rounds=rounds)
        messages.append(msg)  # the assistant's tool-call message
        for call in calls:      # a complex ask may fan out to several calls a round
            result, entry, call_id = _dispatch_call(ctx, by_name, call)
            trace.append(entry)
            messages.append({"role": "tool", "tool_call_id": call_id,
                             "content": json.dumps(result, default=str)})
    # bound hit: ask for a final answer with no more tools
    final = llm.chat(messages, tools=None, max_tokens=REPLY_TOKENS)
    return Turn(reply=final.get("content") or "(no answer within tool budget)",
                trace=trace, rounds=MAX_ROUNDS)
