"""Routines auto-run: `routines.run_due` executes a due routine through the
assistant's fenced loop, lands the narration as a dated document, and ticks it.

The LLM is external/non-deterministic, so it's a scripted fake (the same shape
`test_assistant.py` uses) that emits one tool call then a final answer. That
lets the booktest prove the auto-run contract without a real model: a *due*
routine runs, an *un-due* one is skipped, the result is recorded as a document
tagged with the `routine` topic (the journal was retired into documents,
.ai/tasks/15 Phase 2d), and the routine's `last_done` advances so it stops being
due — the closed loop, unattended. Requires a running Aito instance.
"""

import json
from datetime import date

import booktest as bt

from company_ai import loaders, routines
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

AS_OF = date(2026, 6, 17)   # a Wednesday


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _load(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_touches(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_routines(client, SEED_DIR)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)  # reset the store to a known state
    # the shared booktest env persists between runs, so this reload clears any
    # document an earlier run recorded — the seed carries no `routine`-topic
    # documents, so the only ones after run_due are the ones this test produced.


def _tool_call(call_id: str, name: str, args: dict) -> dict:
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": call_id, "type": "function",
         "function": {"name": name, "arguments": json.dumps(args)}}]}


class ScriptedLLM:
    """Returns the queued messages in order (same fake as the assistant test)."""
    model = "scripted"

    def __init__(self, script):
        self.script = list(script)

    def chat(self, messages, tools=None, max_tokens=1024):
        return self.script.pop(0)


def _routine(client, routine_id):
    hits = client.query({"from": "routines", "where": {"routine_id": routine_id}})["hits"]
    assert hits, routine_id
    return hits[0]


def test_run_due_executes_and_records(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)

    # so01 (Monday outreach prep, weekly Mon, never done) is DUE on any day;
    # the scripted model calls one read tool then answers, exactly as the loop
    # would drive the real model. `only` keeps the run to this one routine so
    # the script is deterministic.
    llm = ScriptedLLM([
        _tool_call("c1", "who_to_call", {"window": "1215", "top_n": 3}),
        {"role": "assistant",
         "content": "Top 3 prospects queued for the next outbound batch."},
    ])

    before = _routine(client, "so01")
    t.h1("a due routine runs through the assistant loop")
    res = routines.run_due(client, llm=llm, as_of=AS_OF, only=["so01"])
    t.tln(f"as_of: {res['as_of']}")
    t.tln(f"ran count: {res['count']}")
    for r in res["ran"]:
        t.tln(f"  - {r['routine_id']} {r['title']!r}: "
              f"{r['tool_calls']} tool call(s), {r['rounds']} round(s)")
    t.tln(f"so01 last_done before: {before.get('last_done') or '(never)'}")

    t.h1("the narration landed as a dated document, tagged topic `routine`")
    docs = [d for d in client.query({"from": "documents", "limit": 200})["hits"]
            if "routine" in (d.get("topics") or "")]
    for d in docs:
        t.tln(f"  {d['noted_on']} · kind={d['kind']} · topics={d.get('topics')} · {d['title']!r}")
        t.tln(f"    body: {d['body']}")
    assert len(docs) == 1
    assert docs[0]["title"] == "Routine: Monday outreach prep"
    assert docs[0]["noted_on"] == AS_OF.isoformat(), "the routine document is dated to the run (diary)"

    t.h1("the routine is ticked — it is no longer due (the loop closes)")
    after = _routine(client, "so01")
    t.tln(f"so01 last_done after: {after['last_done']}")
    state = routines.due_state(after, AS_OF)
    t.tln(f"so01 due now: {state['due']}")
    assert after["last_done"] == AS_OF.isoformat()
    assert state["due"] is False


def test_run_due_skips_when_not_due(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)

    # tick so01 today, then ask run_due to run only so01: it is no longer due,
    # so nothing runs and the LLM is never consulted (an empty script would
    # raise on .pop if it were).
    from company_ai import log
    log.tick_routine(client, "so01", as_of=AS_OF)
    llm = ScriptedLLM([])

    t.h1("run_due skips a routine that isn't due (no LLM call, no document)")
    res = routines.run_due(client, llm=llm, as_of=AS_OF, only=["so01"])
    t.tln(f"ran count: {res['count']}")
    t.tln(f"ran: {res['ran']}")
    assert res["count"] == 0


def test_run_routine_forces_a_not_due_routine(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)

    # tick so01 today so it is NOT due, then run it on demand. The "Run" button /
    # MCP tool default to force=True — an explicit run means run it now.
    from company_ai import log
    log.tick_routine(client, "so01", as_of=AS_OF)
    llm = ScriptedLLM([
        _tool_call("c1", "who_to_call", {"window": "1215", "top_n": 3}),
        {"role": "assistant", "content": "Re-ran the batch on demand."},
    ])

    t.h1("run_routine(force=True) runs a not-due routine on demand")
    before = _routine(client, "so01")
    t.tln(f"so01 due before: {routines.due_state(before, AS_OF)['due']}")
    res = routines.run_routine(client, "so01", llm=llm, as_of=AS_OF)
    t.tln(f"ran: {res['ran']} · {res['tool_calls']} tool call(s), {res['rounds']} round(s)")
    t.tln(f"reply: {res['reply']}")
    t.tln(f"document_id set: {bool(res['document_id'])}")
    assert res["ran"] is True

    t.h1("with force=False a not-due routine is skipped (no LLM call)")
    skip = routines.run_routine(client, "so01", llm=ScriptedLLM([]),
                                as_of=AS_OF, force=False)
    t.tln(f"ran: {skip['ran']} · skipped: {skip.get('skipped')}")
    assert skip["ran"] is None and skip["skipped"] == "not due"
