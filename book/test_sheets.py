"""Data-sheet gate: the raw table browser. Unlike the analytics views, a
sheet returns every row of a table — including the old/closed cases.
Requires a running Aito instance.
"""

import booktest as bt

from company_ai import loaders, sheets
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def test_table_sheet_shows_all_rows(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_deals(client, SEED_DIR)

    t.h1("deals sheet — every row, closed cases included")
    sheet = sheets.table_sheet(client, "deals")
    t.tln(f"columns: {sheet['columns']}")
    t.tln(f"total={sheet['total']} shown={sheet['shown']} truncated={sheet['truncated']}")
    stages = sorted({r["stage"] for r in sheet["rows"]})
    t.tln(f"stages present (unfiltered): {stages}")
    assert any(s.startswith("closed_") for s in stages), \
        "a raw sheet must include closed/old cases, unlike the open pipeline"
    # schema order, stable by id
    ids = [r["deal_id"] for r in sheet["rows"]]
    assert ids == sorted(ids), "rows not stably ordered by id"
    t.tln(f"first/last id: {ids[0]} .. {ids[-1]}")


def test_scoped_sheet(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_todos(client, SEED_DIR)

    t.h1("a view's own data tab: todos scoped to one area")
    scoped = sheets.table_sheet(client, "todos", where={"area": "operations"})
    areas = sorted({r["area"] for r in scoped["rows"]})
    t.tln(f"where area=operations -> total={scoped['total']} areas present={areas}")
    assert areas == ["operations"], "scoped sheet must contain only the requested slice"

    t.h1("a surprising where column raises, never silently returns everything")
    try:
        sheets.table_sheet(client, "todos", where={"nope": "x"})
        raise RuntimeError("accepted an unknown where column")
    except AssertionError as e:
        t.tln(str(e))


def test_unknown_table_asserts(t: bt.TestCaseRun) -> None:
    t.h1("Sheeting an unknown table raises")
    try:
        sheets.table_sheet(_client(), "invoices")
        raise RuntimeError("sheeted an unknown table")
    except AssertionError as e:
        t.tln(str(e))
