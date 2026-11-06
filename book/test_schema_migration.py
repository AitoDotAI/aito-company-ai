"""Schema-migration gate: create_schema brings an existing table up to the
code's definition by adding missing columns (Aito's per-column API), not by
dropping and reloading. Requires a running Aito instance.
"""

import booktest as bt

from company_ai import loaders, schema
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def test_create_schema_adds_missing_column(t: bt.TestCaseRun) -> None:
    client = _client()
    # start from a fully-loaded deals table
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)   # the company_id link target
    loaders.load_deals(client, SEED_DIR)

    t.h1("Simulate an old instance: drop the derived `won` column")
    # deals carries a `company_id` link, and Aito's declarative `_apply` can't
    # re-declare a link on a populated table, so the client drops the column via a
    # row-preserving reload (.ai/tasks/05 note 9). Rows survive; `won` is gone —
    # an old instance that predates the column. rows_after_drop is captured HERE so
    # the no-reload assertion below measures create_schema alone, not the setup.
    client.delete_column("deals", "won")
    have = set(client.get_schema()["schema"]["deals"]["columns"])
    rows_after_drop = client.count("deals")
    t.tln(f"`won` present after drop: {'won' in have}")
    t.tln(f"rows preserved through the drop: {rows_after_drop}")

    t.h1("create_schema re-adds the missing column IN PLACE, no reload")
    report = loaders.create_schema(client)
    t.tln(f"created tables: {report['created_tables'] or 'none'}")
    t.tln(f"added columns:  {report['added_columns'] or 'none'}")

    have = set(client.get_schema()["schema"]["deals"]["columns"])
    assert "won" in have, "`won` was not re-added"
    assert client.count("deals") == rows_after_drop, "rows changed — create_schema reloaded"
    t.tln(f"`won` present again: {'won' in have}; rows unchanged: {client.count('deals')}")
    t.tln("note: re-added column reads null on existing rows until reloaded")


def test_create_schema_idempotent_and_reports_extras(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)

    t.h1("Re-running create_schema on an up-to-date schema is a no-op")
    report = loaders.create_schema(client)
    t.tln(f"created: {report['created_tables'] or 'none'}, "
          f"added: {report['added_columns'] or 'none'}")

    t.h1("An extra live column is reported, never dropped")
    client.add_column("deals", "scratch_note", {"type": "String", "nullable": True})
    report = loaders.create_schema(client)
    t.tln(f"extra_columns: {report['extra_columns']}")
    assert "scratch_note" in client.get_schema()["schema"]["deals"]["columns"], \
        "extra column was dropped — it should be left in place"
    client.delete_column("deals", "scratch_note")  # cleanup
    t.tln("extra column left in place (surfaced, not dropped)")


class _Recorder(AitoClient):
    """Records the requests create_table would send; talks to no engine."""

    def __init__(self) -> None:
        super().__init__("http://recorder.invalid", "")
        self.sent: list[tuple[str, str, dict]] = []

    def _request(self, method, path, body=None, **kwargs):
        self.sent.append((method, path, body))
        return {"status": "recorded"}


def test_schema_declares_what_create_table_sends(t: bt.TestCaseRun) -> None:
    """docs/38: AitoClient.create_table sends "type": "collection" whatever
    schema.py declares, and every internal table is on the v2 engine. So
    schema.py declares "collection" too. The payload each table's create
    sends is pinned by its digest, which must be identical before and after
    the declaration changes; and the definition is now sent as written."""
    import hashlib
    import json

    rec = _Recorder()
    for name, definition in schema.TABLES.items():
        rec.create_table(name, definition)
    t.h1("What create_table sends, per table (sha256 of the canonical JSON)")
    as_written = []
    for (method, path, body), (name, definition) in zip(rec.sent, schema.TABLES.items()):
        digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
        t.tln(f"  {method} {path:40} type={body['type']:10} {digest}")
        as_written.append(body == definition)
    declared = sorted({d["type"] for d in schema.TABLES.values()})
    t.h1("What schema.py declares")
    t.tln(f"  {declared}")
    assert declared == ["collection"], f"schema.py declares {declared}; create_table sends collection"
    assert all(as_written), "a definition is not sent as written"
