"""Recurring agentic routines (docs/18-routines.md).

A routine is a recurring task with a cadence (daily / weekly+weekday /
monthly+day) and a `prep` recipe. Two jobs:

  - **due-ness** — computed from the cadence and `last_done` (no scheduler in
    the repo, rule 1): the current period's scheduled date, whether it's due,
    and whether it's overdue. Ticking it stamps `last_done`.
  - **prepare** — the agentic part, kept rule-1-clean: the app gathers
    Aito-grounded data and fills a *prompt for Claude (Desktop)* to run — it
    does not run an agent loop itself. `prep=prospects` pulls Aito-ranked
    candidates (who_to_call) for the next outreach batch (e.g. La Growth
    Machine); `prep=brief` produces the week-prep prompt; `none` uses the
    routine's own template. Every figure handed over is Aito's.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from . import queries, schema
from .aito import AitoClient


def _scheduled(routine: dict, as_of: date) -> date:
    """The most recent occurrence of this routine on or before `as_of`."""
    cadence = routine["cadence"]
    if cadence == "daily":
        return as_of
    if cadence == "weekly":
        target = schema.WEEKDAYS.index(routine["weekday"])  # 0=Mon
        back = (as_of.weekday() - target) % 7
        return as_of - timedelta(days=back)
    # monthly: this month's day_of_month if reached, else last month's
    dom = routine["day_of_month"]
    if as_of.day >= dom:
        return as_of.replace(day=dom)
    prev = as_of.replace(day=1) - timedelta(days=1)
    return prev.replace(day=dom)


def due_state(routine: dict, as_of: date) -> dict:
    scheduled = _scheduled(routine, as_of)
    last = date.fromisoformat(routine["last_done"]) if routine.get("last_done") else None
    due = last is None or last < scheduled
    return {
        "scheduled": scheduled.isoformat(),
        "due": due,
        "overdue": due and scheduled < as_of,
        "days_overdue": (as_of - scheduled).days if due else 0,
    }


@dataclass
class Result:
    calls: list = field(default_factory=list)
    derived: dict | None = None


def board(client: AitoClient, as_of: date | None = None) -> Result:
    """The active routines, each with its due state; due ones first."""
    as_of = as_of or date.today()
    result = Result()
    request = {"from": "routines", "where": {"active": True}, "limit": 1000}
    response = client.query(request)
    result.calls.append(("_query", request, response))
    rows = []
    for r in response["hits"]:
        rows.append({**r, **due_state(r, as_of)})
    rows.sort(key=lambda r: (not r["due"], -r["days_overdue"], r["title"]))
    result.derived = {"as_of": as_of.isoformat(), "routines": rows}
    return result


def _prospect_pack(client: AitoClient, result: Result, routine: dict, as_of: date) -> dict:
    """Aito-ranked candidates for the next outreach batch + a Claude-Desktop
    prompt to load them (e.g. into your outreach tool) and draft openers."""
    q = queries.who_to_call(client, "1215", top_n=10, as_of=as_of)
    result.calls.extend(q.calls)
    candidates = q.derived
    lines = "\n".join(
        f"  - {c['contact_id']} · {c['company']} · P(good)≈{round(c['$p'], 2)}"
        for c in candidates)
    prompt = (
        f"Prepare the next outreach batch for “{routine['title']}”.\n\n"
        f"Aito ranked these {len(candidates)} prospects by probability of a good "
        f"outcome right now (highest first):\n{lines}\n\n"
        "For each prospect: call opener_context(<contact_id>) and draft a one-line "
        "opener grounded in the retrieved evidence. Then produce the import list "
        "(company, opener) ready to paste into your outreach tool. Skip anyone "
        "already in an active sequence. Keep it to these — they're the ones Aito "
        "ranks worth contacting this round.")
    return {"candidates": candidates, "prompt": prompt}


def prepare(client: AitoClient, routine: dict, as_of: date | None = None) -> Result:
    """Build the run pack for a routine: the Aito-grounded data + a prompt to
    run in Claude (Desktop, which has the MCP tools). The app prepares; Claude
    runs (rule 1)."""
    as_of = as_of or date.today()
    result = Result()
    prep = routine["prep"]
    if prep == "prospects":
        result.derived = _prospect_pack(client, result, routine, as_of)
    elif prep == "brief":
        result.derived = {
            "candidates": [],
            "prompt": (f"{routine['title']}: prepare the upcoming week per "
                       "prompts/week-prep.md (MODE: plan). Use the MCP tools "
                       "(todos_now, deal_pipeline, who_to_call, experiment_board) "
                       "to ground every number; respect the protected calendar."),
        }
    else:  # none — the routine's own template, or its title
        result.derived = {"candidates": [],
                          "prompt": routine.get("prompt") or routine["title"]}
    return result


def _execute(client: AitoClient, routine: dict, *, llm=None,
             as_of: date | None = None) -> dict:
    """Run ONE routine through the assistant loop and record it. Shared by the
    scheduled/CLI batch (`run_due`) and the on-demand single run (`run_routine`).

    Rule-1 scope (a third named exception — see CLAUDE.md rule 1 and docs/18):
    this reuses the assistant's fence exactly. `assistant.run_turn` may call only
    the read-only tools, narrates their results, is bounded (MAX_ROUNDS), and
    never computes a ranking, score, or prediction itself (Aito does). The
    routine prepares and narrates — its output is a dated document (the diary
    lane, docs/25; the journal is retired, .ai/tasks/15 Phase 2d); it does not
    act (no outbound; that stays parked). One model runs here, the swappable
    provider in llm.py.
    """
    from . import assistant, log      # local import: assistant pulls heavier deps
    as_of = as_of or date.today()
    pack = prepare(client, routine, as_of=as_of).derived
    # search=None, fetch=None: the routines runner is UNATTENDED, so it gets the
    # Aito read tools but NOT the outbound web tools. That removes the exfiltration
    # channel (a prompt-injected document/page can't make an unattended loop POST
    # internal data to an external URL) and the LLM-cost-abuse surface. The
    # interactive assistant keeps the web tools (a human is present).
    turn = assistant.run_turn(
        [{"role": "user", "content": pack["prompt"]}],
        client=client, llm=llm, as_of=as_of, search=None, fetch=None)
    area = routine.get("area")
    entry = log.add_document(
        client, title=f"Routine: {routine.get('title') or routine['routine_id']}",
        body=turn.reply, kind="internal", noted_on=as_of.isoformat(),
        topics="routine" + (f";{area}" if area else ""))
    log.tick_routine(client, routine["routine_id"], as_of=as_of)
    return {"routine_id": routine["routine_id"], "title": routine.get("title"),
            "reply": turn.reply, "document_id": entry["doc_id"],
            "tool_calls": len(turn.trace), "rounds": turn.rounds}


def run_due(client: AitoClient, *, llm=None, as_of: date | None = None,
            only: list[str] | None = None, force: bool = False) -> dict:
    """Auto-run every DUE routine: execute its prepared prompt through the
    assistant's bounded, read-only tool loop, record the result as a dated
    document, and tick the routine (see `_execute` for the rule-1 fence).

    Scheduling is an OS timer (`ops/company-ai-routines.*`), NOT an in-app
    scheduler. `only` limits the run to those routine_ids; `force` runs them
    even when not due (a deliberate re-run — the timer never sets it).
    """
    as_of = as_of or date.today()
    ran = []
    for r in board(client, as_of=as_of).derived["routines"]:
        if only is not None and r["routine_id"] not in only:
            continue
        if not force and not r.get("due"):
            continue
        ran.append(_execute(client, r, llm=llm, as_of=as_of))
    return {"as_of": as_of.isoformat(), "count": len(ran), "ran": ran}


def run_routine(client: AitoClient, routine_id: str, *, llm=None,
                as_of: date | None = None, force: bool = True) -> dict:
    """Run ONE routine on demand (the dashboard "Run" button / MCP `run_routine`).
    Defaults to `force=True` — an explicit click/call means run it now, even if
    it isn't due. With `force=False` a not-due routine is skipped (ran=None),
    so the caller can honour due-ness. Returns the `_execute` record (or None)."""
    as_of = as_of or date.today()
    match = [r for r in board(client, as_of=as_of).derived["routines"]
             if r["routine_id"] == routine_id]
    assert match, f"unknown routine_id {routine_id!r}"
    routine = match[0]
    if not force and not routine.get("due"):
        return {"routine_id": routine_id, "title": routine.get("title"),
                "ran": None, "skipped": "not due"}
    return {**_execute(client, routine, llm=llm, as_of=as_of), "ran": True}
