"""Assistant gate: the bounded, Aito-backed tool-calling loop.

The real model is external/non-deterministic, so the LLM here is a scripted
fake that emits tool calls then a final answer. That lets the booktest prove
the parts that must hold: the loop executes the requested Aito-backed tool,
feeds the *real* Aito result back to the model (grounding), surfaces tool
errors instead of swallowing them (rule 3), and respects the round bound.
Requires a running Aito instance.
"""

import json
from datetime import date

import booktest as bt

from company_ai import assistant, loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config
from company_ai.webfetch import FetchError, Page, _extract, _guard_url
from company_ai.websearch import SearchError, SearchResult

AS_OF = date(2026, 6, 17)


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _load(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_touches(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)


def _tool_call(call_id: str, name: str, args: dict) -> dict:
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": call_id, "type": "function",
         "function": {"name": name, "arguments": json.dumps(args)}}]}


def _raw_tool_call(call_id: str, name: str, raw_arguments: str) -> dict:
    """A tool_call whose `arguments` is a raw string — used to reproduce the
    malformed/truncated JSON a complex request can provoke from the model."""
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": call_id, "type": "function",
         "function": {"name": name, "arguments": raw_arguments}}]}


def _multi_tool_call(*calls) -> dict:
    """An assistant message that fans out to several tool calls at once (a
    complex ask). Each `calls` item is (call_id, name, args)."""
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": cid, "type": "function",
         "function": {"name": n, "arguments": json.dumps(a)}} for cid, n, a in calls]}


def _ctx(search=None, fetch=None):
    """A ToolContext for the availability/spec tests (no Aito call needed)."""
    return assistant.ToolContext(aito=None, as_of=AS_OF, search=search, fetch=fetch)


class ScriptedLLM:
    """Returns the queued messages in order; records every messages list it
    was handed (so a test can inspect the grounding fed back to the model)."""
    model = "scripted"

    def __init__(self, script):
        self.script = list(script)
        self.seen = []
        self.budgets = []   # the max_tokens run_turn asked for, per call

    def chat(self, messages, tools=None, max_tokens=1024):
        self.seen.append(messages)
        self.budgets.append(max_tokens)
        return self.script.pop(0)


class ScriptedSearch:
    """A deterministic web-search backend for the booktest: returns canned
    results and records each query. Stands in for the real Brave provider so
    the loop's *use* of search is tested without a network call or key."""
    provider = "scripted"

    def __init__(self, results, fail=False):
        self.results = results
        self.fail = fail
        self.queries = []

    def search(self, query, count=5):
        self.queries.append((query, count))
        if self.fail:
            raise SearchError("Brave search -> 429: rate limited")
        return self.results[:count]


class ScriptedFetch:
    """A deterministic page fetcher for the booktest: returns a canned Page and
    records the urls asked for. Stands in for the real (network) Fetcher."""

    def __init__(self, page, fail=False):
        self.page = page
        self.fail = fail
        self.urls = []

    def fetch(self, url, max_chars=None):
        self.urls.append(url)
        if self.fail:
            raise FetchError("fetch https://blocked.example -> 403")
        return self.page


def test_calls_tool_and_grounds(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    llm = ScriptedLLM([
        _tool_call("c1", "deal_pipeline", {}),
        {"role": "assistant", "content": "You have open deals worth tracking."},
    ])

    t.h1("assistant: tool call → Aito result fed back → final answer")
    turn = assistant.run_turn(
        [{"role": "user", "content": "How's my pipeline?"}],
        client=client, llm=llm, as_of=AS_OF)
    t.tln(f"reply: {turn.reply}")
    t.tln(f"rounds: {turn.rounds}")
    t.tln(f"trace: {turn.trace}")

    # the second LLM call must have been handed the real Aito result as a tool
    # message — proof the answer is grounded, not invented.
    final_messages = llm.seen[-1]
    tool_msg = next(m for m in final_messages if m.get("role") == "tool")
    grounded = json.loads(tool_msg["content"])
    t.tln(f"grounding: deal_pipeline returned open_deals="
          f"{grounded['kpis']['open_deals']} (the number the model must use)")
    assert turn.trace == [{"tool": "deal_pipeline", "args": {}, "ok": True}]


def test_tool_args_threaded(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    llm = ScriptedLLM([
        _tool_call("c1", "who_to_call", {"window": "1215", "top_n": 3}),
        {"role": "assistant", "content": "Three contacts to call at 12:15."},
    ])

    t.h1("assistant: tool arguments are threaded through to the Aito query")
    turn = assistant.run_turn(
        [{"role": "user", "content": "Who should I call at lunch?"}],
        client=client, llm=llm, as_of=AS_OF)
    t.tln(f"trace: {turn.trace}")
    tool_msg = next(m for m in llm.seen[-1] if m.get("role") == "tool")
    queue = json.loads(tool_msg["content"])
    t.tln(f"who_to_call(1215, top_n=3) returned {len(queue)} ranked contacts")
    assert turn.trace[0]["args"] == {"window": "1215", "top_n": 3}


def test_tool_error_is_surfaced_not_raised(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    # an invalid window makes the underlying query assert; the loop must feed
    # the error back to the model, not crash the turn (rule 3).
    llm = ScriptedLLM([
        _tool_call("c1", "who_to_call", {"window": "midnight"}),
        {"role": "assistant", "content": "That window isn't valid — try 0800, 1215, or 1600."},
    ])

    t.h1("assistant: a tool error is surfaced to the model, never swallowed")
    turn = assistant.run_turn(
        [{"role": "user", "content": "Who should I call at midnight?"}],
        client=client, llm=llm, as_of=AS_OF)
    entry = turn.trace[0]
    t.tln(f"trace ok={entry['ok']} error={entry['error']}")
    tool_msg = next(m for m in llm.seen[-1] if m.get("role") == "tool")
    t.tln(f"error handed back to model: {tool_msg['content']}")
    assert entry["ok"] is False and "midnight" in entry["error"]


def test_unknown_tool_surfaced(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    llm = ScriptedLLM([
        _tool_call("c1", "delete_everything", {}),
        {"role": "assistant", "content": "I can't do that."},
    ])
    t.h1("assistant: a hallucinated tool name is reported, not executed")
    turn = assistant.run_turn(
        [{"role": "user", "content": "drop the database"}],
        client=client, llm=llm, as_of=AS_OF)
    t.tln(f"trace: {turn.trace}")
    assert turn.trace[0]["ok"] is False
    assert "unknown tool" in turn.trace[0]["error"]


def test_complex_malformed_arguments_do_not_crash_the_turn(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    # a complex ask makes the model emit a bigger tool call; here its JSON
    # arguments are truncated. Before, json.loads crashed the whole turn (the
    # parse was outside any guard) — the request just failed. Now it's surfaced.
    llm = ScriptedLLM([
        _raw_tool_call("c1", "who_to_call", '{"window": "1215", "top_n":'),
        {"role": "assistant", "content": "Sorry — let me try that cleanly."},
    ])
    t.h1("assistant: a truncated/malformed tool call is surfaced, not fatal")
    turn = assistant.run_turn(
        [{"role": "user", "content": "who to call at 12:15, prep me for each, and rank them"}],
        client=client, llm=llm, search=None, fetch=None, as_of=AS_OF)
    entry = turn.trace[0]
    t.tln(f"trace ok={entry['ok']} error={entry['error']}")
    tool_msg = next(m for m in llm.seen[-1] if m.get("role") == "tool")
    t.tln(f"error handed back to model: {tool_msg['content']}")
    t.tln(f"reply: {turn.reply!r}")
    assert entry["ok"] is False and "parse" in entry["error"]
    assert turn.reply and turn.reply != "(the assistant returned an empty reply)"


def test_complex_request_fans_out_to_several_tool_calls(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    llm = ScriptedLLM([
        _multi_tool_call(("c1", "deal_pipeline", {}), ("c2", "todos_now", {})),
        {"role": "assistant", "content": "Pipeline and today's actions, together."},
    ])
    t.h1("assistant: several tool calls in one round are all run and grounded")
    turn = assistant.run_turn(
        [{"role": "user", "content": "give me the pipeline AND my most urgent actions"}],
        client=client, llm=llm, search=None, fetch=None, as_of=AS_OF)
    t.tln(f"tools run: {[e['tool'] for e in turn.trace]}")
    tool_msgs = [m for m in llm.seen[-1] if m.get("role") == "tool"]
    t.tln(f"tool results handed back before the answer: {len(tool_msgs)}")
    assert [e["tool"] for e in turn.trace] == ["deal_pipeline", "todos_now"]
    assert len(tool_msgs) == 2


def test_structurally_broken_tool_call_is_surfaced(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    # a tool_call with no function/name/id at all — must not KeyError the turn
    broken = {"role": "assistant", "content": None, "tool_calls": [{"type": "function"}]}
    llm = ScriptedLLM([broken, {"role": "assistant", "content": "recovered"}])
    t.h1("assistant: a structurally broken tool_call is surfaced, not fatal")
    turn = assistant.run_turn(
        [{"role": "user", "content": "do something complex"}],
        client=client, llm=llm, search=None, fetch=None, as_of=AS_OF)
    t.tln(f"trace: {turn.trace}")
    t.tln(f"reply: {turn.reply}")
    assert turn.trace[0]["ok"] is False
    assert turn.reply == "recovered"


def test_round_bound(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    # a model that never stops calling tools must be cut off at MAX_ROUNDS.
    never_stops = [_tool_call(f"c{i}", "what_changed", {}) for i in range(assistant.MAX_ROUNDS + 3)]
    never_stops.append({"role": "assistant", "content": "final"})
    llm = ScriptedLLM(never_stops)

    t.h1(f"assistant: the tool loop is bounded at MAX_ROUNDS={assistant.MAX_ROUNDS}")
    turn = assistant.run_turn(
        [{"role": "user", "content": "loop forever"}], client=client, llm=llm, as_of=AS_OF)
    t.tln(f"rounds={turn.rounds} tool calls in trace={len(turn.trace)} reply={turn.reply!r}")
    assert turn.rounds == assistant.MAX_ROUNDS
    assert len(turn.trace) == assistant.MAX_ROUNDS


def test_reply_budget_is_generous(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    llm = ScriptedLLM([
        _tool_call("c1", "deal_pipeline", {}),
        {"role": "assistant", "content": "done"},
    ])
    t.h1("assistant: every round gets a generous reply budget (reasoning models)")
    # On a reasoning model the hidden reasoning tokens count against max_tokens,
    # so a small budget (the SDK default 1024) is fully consumed by reasoning
    # after a tool result — the model returns empty content and the turn dies
    # with no answer. run_turn must ask for REPLY_TOKENS, not the default.
    assistant.run_turn([{"role": "user", "content": "How's my pipeline?"}],
                       client=client, llm=llm, as_of=AS_OF)
    t.tln(f"REPLY_TOKENS = {assistant.REPLY_TOKENS}")
    t.tln(f"budgets requested per round: {llm.budgets}")
    assert all(b == assistant.REPLY_TOKENS for b in llm.budgets)
    assert assistant.REPLY_TOKENS >= 4096


_HITS = [
    SearchResult(title="Northwind posts record Q2", url="https://news.example/northwind-q2",
                 snippet="The ERP vendor reported 18% growth…", age="2 days ago"),
    SearchResult(title="Northwind hires new CFO", url="https://news.example/northwind-cfo",
                 snippet="…appointed effective next month.", age="1 week ago"),
]


def test_web_search_tool_grounds_on_results(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    search = ScriptedSearch(_HITS)
    llm = ScriptedLLM([
        _tool_call("c1", "web_search", {"query": "Northwind news", "count": 2}),
        {"role": "assistant", "content": "Northwind posted record Q2 growth and hired a CFO."},
    ])

    t.h1("assistant: web_search runs, external results are fed back, answer cites them")
    turn = assistant.run_turn(
        [{"role": "user", "content": "Any recent news on Northwind?"}],
        client=client, llm=llm, search=search, as_of=AS_OF)
    t.tln(f"query sent to the backend: {search.queries}")
    t.tln(f"reply: {turn.reply}")
    t.tln(f"trace: {turn.trace}")
    # the tool result handed back must carry the web hits (grounding)
    tool_msg = next(m for m in llm.seen[-1] if m.get("role") == "tool")
    grounded = json.loads(tool_msg["content"])
    t.tln(f"grounding: web_search returned {len(grounded['results'])} results, "
          f"first url={grounded['results'][0]['url']}")
    # the system prompt gains the web-search note only when search is available
    t.tln(f"system mentions web_search: {'web_search' in llm.seen[0][0]['content']}")
    assert turn.trace[0] == {"tool": "web_search",
                             "args": {"query": "Northwind news", "count": 2}, "ok": True}


def test_web_search_error_is_surfaced(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    search = ScriptedSearch(_HITS, fail=True)  # the backend errors (e.g. 429)
    llm = ScriptedLLM([
        _tool_call("c1", "web_search", {"query": "market size"}),
        {"role": "assistant", "content": "Web search is unavailable right now."},
    ])

    t.h1("assistant: a web_search backend error is surfaced to the model, not swallowed")
    turn = assistant.run_turn(
        [{"role": "user", "content": "How big is the market?"}],
        client=client, llm=llm, search=search, as_of=AS_OF)
    entry = turn.trace[0]
    t.tln(f"trace ok={entry['ok']} error={entry['error']}")
    tool_msg = next(m for m in llm.seen[-1] if m.get("role") == "tool")
    t.tln(f"error handed back to model: {tool_msg['content']}")
    assert entry["ok"] is False and "429" in entry["error"]


def test_allowlist_curates_the_registry(t: bt.TestCaseRun) -> None:
    t.h1("COMPANY_AI_ASSISTANT_TOOLS narrows the tool surface (the OSS seam)")
    ctx = _ctx(search=object(), fetch=object())
    everything = [tool.name for tool in assistant.active_tools(ctx)]
    curated = [tool.name for tool in
               assistant.active_tools(ctx, allow=["deal_pipeline", "web_search"])]
    t.tln(f"all available tools: {len(everything)}")
    t.tln(f"curated to allowlist: {curated}")
    assert set(curated) == {"deal_pipeline", "web_search"}
    # an unknown name in the allowlist simply doesn't appear (no crash)
    assert [tool.name for tool in assistant.active_tools(ctx, allow=["nope"])] == []


def test_fetch_page_tool_reads_a_page(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    page = Page(url="https://northwind.example.com/pricing", title="Northwind — Pricing",
                text="Plans start at €49 per user per month.", truncated=False)
    fetch = ScriptedFetch(page)
    llm = ScriptedLLM([
        _tool_call("c1", "fetch_page", {"url": "https://northwind.example.com/pricing"}),
        {"role": "assistant", "content": "Northwind lists pricing from €49/user/month."},
    ])

    t.h1("assistant: fetch_page reads a page, its text is fed back, answer cites it")
    turn = assistant.run_turn(
        [{"role": "user", "content": "What does northwind.example.com/pricing say?"}],
        client=client, llm=llm, search=None, fetch=fetch, as_of=AS_OF)
    t.tln(f"url fetched: {fetch.urls}")
    t.tln(f"reply: {turn.reply}")
    t.tln(f"trace: {turn.trace}")
    tool_msg = next(m for m in llm.seen[-1] if m.get("role") == "tool")
    grounded = json.loads(tool_msg["content"])
    t.tln(f"grounding: page title={grounded['title']!r} text={grounded['text']!r}")
    t.tln(f"system mentions fetch_page: {'fetch_page' in llm.seen[0][0]['content']}")
    assert turn.trace[0] == {"tool": "fetch_page",
                             "args": {"url": "https://northwind.example.com/pricing"}, "ok": True}


def test_fetch_page_error_is_surfaced(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    fetch = ScriptedFetch(None, fail=True)  # the fetch fails (e.g. 403)
    llm = ScriptedLLM([
        _tool_call("c1", "fetch_page", {"url": "https://blocked.example"}),
        {"role": "assistant", "content": "I couldn't read that page."},
    ])

    t.h1("assistant: a fetch_page error is surfaced to the model, not swallowed")
    turn = assistant.run_turn(
        [{"role": "user", "content": "Read blocked.example"}],
        client=client, llm=llm, search=None, fetch=fetch, as_of=AS_OF)
    entry = turn.trace[0]
    t.tln(f"trace ok={entry['ok']} error={entry['error']}")
    assert entry["ok"] is False and "403" in entry["error"]


def test_fetch_guard_blocks_internal_addresses(t: bt.TestCaseRun) -> None:
    t.h1("fetch_page's SSRF guard: only public http(s) addresses are allowed")
    # IP literals skip DNS, so this is deterministic and needs no network.
    cases = [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata — the danger
        "http://127.0.0.1:8770/",                     # loopback
        "http://10.1.2.3/internal",                   # private
        "http://[::1]/",                              # ipv6 loopback
        "http://0.0.0.0/",                            # unspecified
        "ftp://example.com/x",                        # non-http scheme
        "https://1.1.1.1/",                           # a public address — allowed
    ]
    blocked = set()
    for url in cases:
        try:
            _guard_url(url)
            verdict = "ALLOW"
        except FetchError as exc:
            verdict = "BLOCK"
            blocked.add(url)
            t.tln(f"  {url}\n      -> BLOCK: {exc}")
            continue
        t.tln(f"  {url}\n      -> {verdict}")
    assert "https://1.1.1.1/" not in blocked          # public is allowed
    assert blocked == set(cases) - {"https://1.1.1.1/"}  # everything else refused


def test_fetch_extracts_readable_text(t: bt.TestCaseRun) -> None:
    t.h1("fetch_page's HTML → text: title kept, script/style dropped, blocks kept")
    html = ("<html><head><title>  Setup — Docs </title><style>.x{color:red}</style>"
            "</head><body><h1>Install</h1><p>Run <code>pip install app</code> first.</p>"
            "<script>track()</script><ul><li>Step one</li><li>Step two</li></ul>"
            "</body></html>")
    title, text = _extract(html)
    t.tln(f"title: {title!r}")
    t.tln("text:")
    t.tln(text)
    assert title == "Setup — Docs"
    assert "track()" not in text and "color:red" not in text  # script/style gone
    assert "Install" in text and "pip install app" in text and "Step two" in text


def test_web_tools_advertised_only_when_enabled(t: bt.TestCaseRun) -> None:
    t.h1("each external web tool is advertised only when its provider is present")
    names = lambda ctx: {tool.name for tool in assistant.active_tools(ctx)}
    base = names(_ctx())
    with_search = names(_ctx(search=object()))
    with_fetch = names(_ctx(fetch=object()))
    t.tln(f"neither: web_search={'web_search' in base} fetch_page={'fetch_page' in base}")
    t.tln(f"search on: adds {sorted(with_search - base)}")
    t.tln(f"fetch on:  adds {sorted(with_fetch - base)}")
    assert "web_search" not in base and "fetch_page" not in base
    assert with_search - base == {"web_search"}
    assert with_fetch - base == {"fetch_page"}


def test_tool_specs_cover_read_surface(t: bt.TestCaseRun) -> None:
    t.h1("the function specs exposed to the model")
    specs = assistant.tool_specs(assistant.active_tools(_ctx(search=object(), fetch=object())))
    for s in specs:
        fn = s["function"]
        t.tln(f"  {fn['name']}({', '.join(fn['parameters']['properties'])})")
    names = {s["function"]["name"] for s in specs}
    # all read tools, no write verbs (no add_/log_/complete_); the web tools read too
    assert not any(n.startswith(("add_", "log_", "complete_", "delete_")) for n in names)
