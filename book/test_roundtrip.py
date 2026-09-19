"""Round-trip gate (docs/04-testing.md gate 3, sacred).

Logging an outcome must visibly change the next brief: the queue
reorders, and the logged contact drops out behind the retouch cooldown.
If this snapshot stops showing a change, the product does not work.
"""

import json
from datetime import date, datetime

import booktest as bt

from company_ai import loaders, log, queries
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

AS_OF = date(2026, 6, 12)


def _queue(result: queries.Result) -> list[str]:
    return [f"{c['contact_id']} {c['name']} $p={c['$p']:.4f}" for c in result.derived]


def test_logged_outcome_changes_queue(t: bt.TestCaseRun) -> None:
    config = Config.from_env()
    client = AitoClient(config.instance_url, config.api_key)
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_touches(client, SEED_DIR)

    t.h1("Queue before")
    before = queries.who_to_call(client, "0800", top_n=5, as_of=AS_OF)
    for line in _queue(before):
        t.tln(line)

    top = before.derived[0]
    t.h1("Log a touch for the top contact")
    row = log.log_touch(
        client,
        contact_id=top["contact_id"],
        channel="call",
        window="0800",
        outcome="conversation",
        next_action="send pricing summary",
        next_action_due="2026-06-15",
        notes="picked up, good chat",
        ts=datetime(2026, 6, 12, 8, 10),
    )
    t.tln(json.dumps(row, sort_keys=True))

    t.h1("Queue after")
    after = queries.who_to_call(client, "0800", top_n=5, as_of=AS_OF)
    for line in _queue(after):
        t.tln(line)

    assert before.derived != after.derived, "logged touch did not change the queue"
    queued_ids = {c["contact_id"] for c in after.derived}
    assert top["contact_id"] not in queued_ids, (
        f"{top['contact_id']} was just touched but is still queued"
    )
    t.tln("")
    t.tln(f"change confirmed: {top['contact_id']} left the queue, order shifted")

    t.h1("The new follow-up appears in what_changed")
    changed = queries.what_changed(client, as_of=AS_OF)
    followups = [
        f for f in changed.derived["follow_ups_due"] if f["contact_id"] == top["contact_id"]
    ]
    assert followups, "logged next_action not in follow-up list"
    t.tln(json.dumps(followups, indent=2, sort_keys=True))
