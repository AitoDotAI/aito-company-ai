"""Migration gate: the read-only `doctor` diagnosis, and the export-all /
load-all round trip used to move an instance's data. The build timestamp is
live (non-deterministic), so it is never snapshotted — only the schema-drift
report, which is deterministic on the seed. Requires a running Aito instance.
"""

import tempfile
from pathlib import Path

import booktest as bt

from company_ai import loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def test_doctor_clean_after_load(t: bt.TestCaseRun) -> None:
    from company_ai import schema
    client = _client()
    loaders.create_schema(client)
    loaders.load_all(client, SEED_DIR)
    # app-state tables (not loaded) — reset to empty so the report is deterministic.
    # (search_items is a v2 view now, not a table — search.py owns it, not the doctor.)
    client.delete_table("search_items")   # drop any leftover view from a search test
    for tbl in ("chat_messages", "changelog", "assignments", "tokens"):
        client.delete_table(tbl)
        client.create_table(tbl, schema.TABLES[tbl])
    # the search trio is linked (impressions -> contexts): drop child-first,
    # create parent-first, or Aito refuses to drop the linked-into table.
    for tbl in ("search_impressions", "search_contexts"):
        client.delete_table(tbl)
    for tbl in ("search_contexts", "search_impressions"):
        client.create_table(tbl, schema.TABLES[tbl])

    t.h1("doctor: a fully loaded instance reports no drift")
    report = loaders.diagnose(client)
    t.tln(f"build reachable: {report['build']['reachable']}")   # value (a timestamp) not snapshotted
    t.tln(f"schema_drift: {report['schema_drift']}")
    for x in report["tables"]:
        t.tln(f"  {x['name']:12} present={x['present']} rows={x['rows']} "
              f"missing_cols={x['missing_columns']}")
    assert report["build"]["reachable"], "version probe should reach a running instance"
    assert not report["schema_drift"], "a fully loaded instance must not report drift"
    assert not report["missing_tables"]


def test_doctor_flags_analyzer_drift(t: bt.TestCaseRun) -> None:
    from company_ai import schema as schema_mod
    client = _client()

    t.h1("doctor catches a column whose analyzer differs from the code")
    # experiments.hypothesis is pinned to 'english' in the code; recreate the
    # table with 'whitespace' to stage the exact mismatch Aito can't fix in
    # place (a recreate+reload migration).
    client.delete_table("experiments")
    defn = {"type": "table", "columns": dict(schema_mod.EXPERIMENTS["columns"])}
    defn["columns"]["hypothesis"] = {"type": "Text", "analyzer": "whitespace"}
    client.create_table("experiments", defn)

    report = loaders.diagnose(client)
    experiments = next(r for r in report["tables"] if r["name"] == "experiments")
    t.tln(f"code wants hypothesis analyzer="
          f"{schema_mod.EXPERIMENTS['columns']['hypothesis']['analyzer']!r}, instance has 'whitespace'")
    t.tln(f"mismatched_columns: {experiments['mismatched_columns']}")
    t.tln(f"schema_drift: {report['schema_drift']}")
    assert experiments["mismatched_columns"], "analyzer drift must be detected"
    # restore for later tests
    client.delete_table("experiments")
    loaders.create_schema(client)
    loaders.load_experiments(client, SEED_DIR)


def test_export_all_load_all_round_trip(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_all(client, SEED_DIR)
    before = {x["name"]: x["rows"] for x in loaders.diagnose(client)["tables"]}

    t.h1("migrate: export every table, then reload from the dump")
    with tempfile.TemporaryDirectory() as tmp:
        exported = loaders.export_all(client, Path(tmp))
        t.tln(f"exported {len(exported)} tables: {[e[0] for e in exported]}")
        restored = loaders.load_all(client, Path(tmp))
    after = {x["name"]: x["rows"] for x in loaders.diagnose(client)["tables"]}

    for table, n in restored:
        t.tln(f"  {table}: {n} rows")
    t.tln(f"row counts preserved across the round trip: {before == after}")
    assert before == after, "export-all -> load-all must preserve every row"
