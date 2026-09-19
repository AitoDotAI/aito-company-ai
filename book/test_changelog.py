"""The change log (docs/22): every meaningful mutation records one entry —
items created and updated (a todo done, a deal won). The round-trip is the
point: acting must show up in the log, which then feeds the assistant, the
advisory board, and (later) note roll-ups.

Timestamps are real, so the snapshot sorts by entity/action/summary and omits
the exact time.
"""

import booktest as bt

from company_ai import changelog, loaders, log, schema
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def test_changelog_records_creations_and_updates(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    # isolate from other runs: start with an empty change log
    client.delete_table("changelog")
    client.create_table("changelog", schema.CHANGELOG)

    t.h1("acting records change-log entries")
    td = log.add_todo(client, area="operations", title="Renew TLS cert", priority=1)
    log.complete_todo(client, td["todo_id"])
    deal = log.add_deal(client, company="Acme Oy", segment="erp", stage="lead",
                        value_eur=12000, probability=20, champion_present=False)
    log.log_deal_update(client, deal["deal_id"], stage="closed_won", probability=100)

    changes = changelog.recent(client)["changes"]
    t.tln(f"entries: {len(changes)}")
    for c in sorted(changes, key=lambda x: (x["entity"], x["action"], x["summary"])):
        t.tln(f"  [{c['entity']}/{c['action']}] {c['summary']}")
    actions = {(c["entity"], c["action"]) for c in changes}
    assert {("todo", "created"), ("todo", "done"),
            ("deal", "created"), ("deal", "won")} <= actions

    t.h1("filter by entity kind")
    deal_changes = changelog.recent(client, entity="deal")["changes"]
    t.tln(f"deal actions: {sorted(c['action'] for c in deal_changes)}")
    assert all(c["entity"] == "deal" for c in deal_changes)
