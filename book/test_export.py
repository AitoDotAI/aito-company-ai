"""Export gate: a table dumps to a CSV that loads straight back (Aito →
files → Aito, the backup/round-trip half of Plane B). Requires a running
Aito instance.
"""

import tempfile
from pathlib import Path

import booktest as bt

from company_ai import loaders, schema
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def test_export_round_trips(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    before = client.count("contacts")

    t.h1("export contacts → CSV → re-load")
    with tempfile.TemporaryDirectory() as tmp:
        path, n = loaders.export_table(client, "contacts", Path(tmp))
        t.tln(f"exported {n} rows to {path.name}")
        t.tln(f"header (loader input columns, no derived): {path.read_text().splitlines()[0]}")
        client.delete_table("contacts")
        client.create_table("contacts", schema.CONTACTS)
        reloaded = loaders.load_rolodex(client, Path(tmp))
        t.tln(f"round-trip counts: before={before} exported={n} reloaded={reloaded}")
        assert before == n == reloaded, "export→load did not round-trip"


def test_export_unknown_table_asserts(t: bt.TestCaseRun) -> None:
    t.h1("Exporting an unknown table raises")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            loaders.export_table(_client(), "invoices", Path(tmp))
            raise RuntimeError("exported an unknown table")
        except AssertionError as e:
            t.tln(str(e))
