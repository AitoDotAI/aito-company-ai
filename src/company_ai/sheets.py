"""Raw table sheets for the data browser.

A read-only spreadsheet over a whole table — every row, unfiltered,
including the old/closed cases the analytics views deliberately leave out
(open pipeline, current funnel). Just a query plus column ordering; no
inference, no derivation. The schema's column order is the sheet's column
order so derived fields sit beside their source.
"""

from . import schema
from .aito import AitoClient

SHEET_LIMIT = 2000
SENSITIVE_TABLES = {"tokens"}   # never rendered as a raw sheet (secret hashes)


def list_tables(client: AitoClient) -> list[dict]:
    """The tables that exist on the instance, with row counts — the picker."""
    live = client.get_schema()["schema"]
    return [
        {"name": name, "count": client.count(name),
         "columns": list(schema.TABLES[name]["columns"])}
        for name in schema.TABLES if name in live and name not in SENSITIVE_TABLES
    ]


def table_sheet(client: AitoClient, table: str, limit: int = SHEET_LIMIT,
                where: dict | None = None) -> dict:
    """Every row of `table` (up to `limit`), in schema column order, sorted by
    the id column so the sheet is stable. `truncated` flags when the table has
    more rows than were returned. An optional `where` scopes the sheet to a
    view's slice (e.g. operations todos) — its columns must exist on the table
    (a surprising key raises, never silently returns everything)."""
    assert table in schema.TABLES, f"unknown table {table!r}; have {sorted(schema.TABLES)}"
    # never expose secret material through the raw sheet, even to the operator —
    # the tokens table holds bearer-token hashes (docs/28); the Admin UI renders
    # tokens without them.
    assert table not in SENSITIVE_TABLES, f"{table!r} is not viewable as a raw sheet"
    limit = max(1, min(int(limit), SHEET_LIMIT))   # cap: an unbounded limit is a query-cost DoS
    columns = list(schema.TABLES[table]["columns"])
    if where:
        unknown = sorted(set(where) - set(columns))
        assert not unknown, f"where keys {unknown} are not columns of {table}"
    request = {"from": table, "limit": limit}
    if where:
        request["where"] = where
    response = client.query(request)
    id_col = columns[0]
    rows = sorted(response["hits"], key=lambda r: str(r.get(id_col, "")))
    return {
        "table": table, "columns": columns, "rows": rows,
        "total": response["total"], "shown": len(rows),
        "truncated": response["total"] > len(rows),
    }
