"""Routines gate: recurring agentic tasks — due-ness computed from cadence +
last_done, and `prepare` building an Aito-grounded run pack for Claude.
Requires a running Aito instance.
"""

from datetime import date

import booktest as bt

from company_ai import loaders, log, routines
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

AS_OF = date(2026, 6, 17)  # a Wednesday


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def test_due_state_by_cadence(t: bt.TestCaseRun) -> None:
    t.h1("Due-ness from cadence + last_done (as_of Wed 2026-06-17)")
    cases = [
        {"cadence": "weekly", "weekday": "mon", "last_done": None},     # this Mon passed, not done → due
        {"cadence": "weekly", "weekday": "mon", "last_done": "2026-06-16"},  # done Tue → covers Mon → not due
        {"cadence": "weekly", "weekday": "fri", "last_done": None},     # Fri not yet reached → last Fri → due
        {"cadence": "monthly", "day_of_month": 1, "last_done": "2026-06-02"},  # done after the 1st → not due
        {"cadence": "daily", "last_done": "2026-06-16"},               # done yesterday → due today
    ]
    for c in cases:
        s = routines.due_state(c, AS_OF)
        t.tln(f"  {c['cadence']:7} {c.get('weekday') or c.get('day_of_month') or '':>3} "
              f"last_done={c['last_done']} → scheduled={s['scheduled']} due={s['due']} overdue={s['overdue']}")


def test_board_and_tick(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_routines(client, SEED_DIR)

    t.h1("Routines board (active, due first)")
    rows = routines.board(client, AS_OF).derived["routines"]
    for r in rows:
        t.tln(f"  {r['title']:24} {r['cadence']}·{r.get('weekday') or r.get('day_of_month')} "
              f"due={r['due']}")

    t.h1("Tick a routine → it's no longer due")
    rid = rows[0]["routine_id"]
    log.tick_routine(client, rid, as_of=AS_OF)
    after = {r["routine_id"]: r for r in routines.board(client, AS_OF).derived["routines"]}
    t.tln(f"{rid} due after tick: {after[rid]['due']}")
    assert after[rid]["due"] is False


def test_prepare_prospects_pack(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_touches(client, SEED_DIR)

    t.h1("Prepare a `prospects` routine → Aito candidates + a Claude prompt")
    routine = {"title": "Monday outreach prep", "prep": "prospects", "prompt": None}
    pack = routines.prepare(client, routine, AS_OF).derived
    t.tln(f"candidates returned: {len(pack['candidates'])}")
    t.tln("prompt mentions the tool the Claude session should call: "
          f"{'opener_context' in pack['prompt']}")
    t.tln("prompt names the routine: "
          f"{'Monday outreach prep' in pack['prompt']}")
    assert pack["candidates"] and "opener_context" in pack["prompt"]
