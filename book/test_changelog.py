"""The change log (docs/22): every meaningful mutation records one entry —
items created and updated (a todo done, a deal won). The round-trip is the
point: acting must show up in the log, which then feeds the assistant
and (later) note roll-ups.

Timestamps are real, so the snapshot sorts by entity/action/summary and omits
the exact time.
"""

from datetime import datetime, timedelta, timezone

import booktest as bt

from book._target import guarded_client
from company_ai import changelog, loaders, log, schema
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR


def _client() -> AitoClient:
    """This book deletes the change log: a test env only, refused before any call."""
    return guarded_client()


def test_changelog_records_creations_and_updates(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    # isolate from other runs: start with an empty change log, and empty
    # todos, or a re-run within log.RETRY_WINDOW finds the previous run's
    # "Renew TLS cert" and add_todo returns it as a retry, recording no
    # "created" entry
    for table, spec in (("changelog", schema.CHANGELOG), ("todos", schema.TODOS)):
        client.delete_table(table)
        client.create_table(table, spec)

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


class _BoundedChangelogAito:
    """An in-memory changelog with the engine's response cap: Aito aborts any
    response over 10 MB, which nginx turns into a 502. At ~2.2 kB a row that
    is ~4,466 rows, so a query asking for more than RESPONSE_ROW_CAP rows on a
    grown table fails here the way it failed in production. Supports the
    subset `recent()` needs: equality and `$gte` in `where`, `{"$desc": f}`
    orderBy, `limit`."""

    RESPONSE_ROW_CAP = 4466

    def __init__(self, rows):
        self.rows = rows
        self.requests = []

    def ensure_table(self, name, definition):
        assert name == "changelog", name

    def query(self, body):
        self.requests.append(body)
        assert body["from"] == "changelog", body

        def matches(r):
            for k, v in body.get("where", {}).items():
                if isinstance(v, dict):
                    assert set(v) == {"$gte"}, v
                    if not r[k] >= v["$gte"]:
                        return False
                elif r[k] != v:
                    return False
            return True

        hits = [r for r in self.rows if matches(r)]
        order = body.get("orderBy")
        if order is not None:
            assert set(order) == {"$desc"}, order
            hits.sort(key=lambda r: r[order["$desc"]], reverse=True)
        limit = body.get("limit", 10)
        if min(limit, len(hits)) > self.RESPONSE_ROW_CAP:
            raise ConnectionError("502 Bad Gateway: response over the 10 MB cap")
        return {"hits": hits[:limit], "total": len(hits)}


def _changelog_rows(n: int) -> list[dict]:
    # stored oldest-first, as an append-only table is; `at` one minute apart
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [{"change_id": f"chg_{i:06d}",
             "at": (start + timedelta(minutes=i)).isoformat(timespec="seconds"),
             "entity": "deal" if i % 3 == 0 else "todo", "entity_id": f"td-{i}",
             "action": "updated", "summary": f"change {i}", "detail": None}
            for i in range(n)]


def test_recent_changes_bounded_on_a_large_changelog(t: bt.TestCaseRun) -> None:
    """recent() on a changelog past the response cap: the request must be
    ordered newest-first and bounded server-side, never 'fetch all and sort
    in Python' (the 502 of 2026-11-03)."""
    fake = _BoundedChangelogAito(_changelog_rows(10000))
    newest = sorted(fake.rows, key=lambda r: r["at"], reverse=True)

    t.h1("default call")
    out = changelog.recent(fake)
    body = fake.requests[-1]
    t.tln(f"request: {body}")
    t.tln(f"count: {out['count']}, returned: {len(out['changes'])}")
    t.tln(f"first: {out['changes'][0]['at']} {out['changes'][0]['summary']}")
    assert body["orderBy"] == {"$desc": "at"}
    assert body["limit"] <= 1000
    assert out["count"] == 10000
    assert [c["at"] for c in out["changes"]] == [r["at"] for r in newest[:50]]

    t.h1("a caller asking for more than the cap is clamped")
    out = changelog.recent(fake, limit=100000)
    body = fake.requests[-1]
    t.tln(f"request: {body}")
    t.tln(f"returned: {len(out['changes'])}")
    assert body["limit"] == 1000
    assert len(out["changes"]) == 1000

    t.h1("entity filter and since window stay server-side")
    since = newest[300]["at"]
    out = changelog.recent(fake, limit=20, entity="deal", since=since)
    body = fake.requests[-1]
    t.tln(f"request: {body}")
    want = [r for r in newest if r["entity"] == "deal" and r["at"] >= since]
    t.tln(f"count: {out['count']}, returned: {len(out['changes'])}")
    assert body["where"] == {"entity": "deal", "at": {"$gte": since}}
    assert out["count"] == len(want)
    assert [c["entity_id"] for c in out["changes"]] == [r["entity_id"] for r in want[:20]]
    assert set(out["changes"][0]) == {"at", "entity", "entity_id", "action", "summary"}


def test_recent_orders_and_windows_on_the_real_engine(t: bt.TestCaseRun) -> None:
    """The bounded recent() leans on Aito for two things the in-memory book
    above only assumes: `orderBy {$desc: "at"}` on a String column, and
    `at: {$gte: since}` on one. Rows go in out of order, so a store-order
    answer can't pass."""
    client = _client()
    client.delete_table("changelog")
    client.create_table("changelog", schema.CHANGELOG)
    ats = ["2026-11-03T09:00:00+00:00", "2026-11-01T12:00:00+00:00", "2026-11-05T08:30:00+00:00",
           "2026-11-02T23:59:59+00:00", "2026-11-04T00:00:00+00:00"]
    client.upload_batch("changelog", [
        {"change_id": f"chg_{i}", "at": at, "entity": "deal" if i % 2 else "todo", "entity_id": f"x{i}",
         "action": "updated", "summary": f"change {i}", "detail": None} for i, at in enumerate(ats)])
    t.h1("Five changes written out of order")
    got = [c["at"] for c in changelog.recent(client, limit=5)["changes"]]
    t.tln(f"  newest first: {got}")
    assert got == sorted(ats, reverse=True), got
    out = changelog.recent(client, limit=2, since="2026-11-03T00:00:00+00:00")
    t.tln(f"  since 3.11, limit 2: {[c['at'] for c in out['changes']]}, count {out['count']}")
    assert [c["at"] for c in out["changes"]] == ["2026-11-05T08:30:00+00:00", "2026-11-04T00:00:00+00:00"]
    assert out["count"] == 3, "count is the whole window, not the page"
    deals = changelog.recent(client, entity="deal")
    t.tln(f"  entity=deal: {[c['at'] for c in deals['changes']]}")
    assert [c["at"] for c in deals["changes"]] == sorted((a for i, a in enumerate(ats) if i % 2), reverse=True)
