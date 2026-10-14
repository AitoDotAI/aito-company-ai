"""Statistical connections: what goes with an outcome (td-20261013103434846142).

The generic sibling of the `predict` escape hatch. `predict` answers "given
these conditions, how likely is X?"; `relate` answers "which field values go
together with X, and how strongly?". Both are one Aito call, so rule 2 holds:
the relation strengths are Aito's `_relate` output, not statistics computed
here. Python only removes fields that would answer the question by
definition, and labels the thin ones.

Each relation carries its support, so a pattern can be told apart from noise:
a lift of 3 on 4 rows is a hint, the same lift on 60 rows is a finding.
"""

from . import schema
from .aito import AitoClient

# Fields that restate the outcome rather than explain it: relating `reached`
# to `outcome=conversation` is true by construction. When the outcome is one of
# these, the others in its group are excluded too.
LEAKS = {
    "touches": {"outcome", "good_outcome", "reached", "booked"},
    "deals": {"stage", "won", "lost_reason"},
    "contacts": {"ever_touched", "ever_reached", "ever_conversation", "ever_meeting"},
    "posts": {"outcome"},
    "sessions": {"signed_up", "started_trial", "converted_paid"},
}
# identity and free-text fields: unique per row, or words rather than values
_ID_SUFFIXES = ("_id", "_thread_id", "_event_id")
_TIME_FIELDS = {"ts", "created", "updated", "date", "noted_on", "next_action_due",
                "last_touch_date", "first_meeting_date", "last_done"}
THIN = 10   # fewer rows than this carry the value: report it, flagged as thin


def read_hit(hit: dict, on: bool) -> dict | None:
    """One `_relate` hit as {field, value, rows_with, rate_with, rate_without}.

    Aito swaps the roles when the relation is scoped with `$on`: without it,
    the outcome is `condition` and the driver `related` (f counts the driver);
    with it, the driver is `condition` and `related` holds the `$on` itself
    (f counts the outcome). Reading an `$on` hit the plain way yields the
    field name "$on" for every row, which is how Segment 360's segment slices
    and the sliced website funnel came to show no causes at all."""
    fs = hit.get("fs", {})
    n, foc = fs.get("n", 0), fs.get("fOnCondition", 0)
    if on:
        driver, rows_with, with_outcome = hit.get("condition", {}), fs.get("fCondition", 0), fs.get("f", 0)
    else:
        driver, rows_with, with_outcome = hit.get("related", {}), fs.get("f", 0), fs.get("fCondition", 0)
    name = next(iter(driver), None)
    if name is None or name.startswith("$"):
        return None
    raw = driver[name]
    return {
        "field": name,
        "value": raw.get("$has") if isinstance(raw, dict) else raw,
        "rows_with": int(rows_with),
        "rate_with": foc / rows_with if rows_with else None,
        "rate_without": (with_outcome - foc) / (n - rows_with) if n - rows_with else None,
        "n": int(n), "with_outcome": int(with_outcome),
    }


def excluded_fields(table: str, outcome_field: str, extra: list[str] | None = None) -> list[str]:
    """The fields a relation over `table` must not report: the outcome itself, its restatements,
    identities, times, and free text. A table or field not in the schema raises."""
    assert table in schema.TABLES, f"unknown table {table!r}; have {sorted(schema.TABLES)}"
    columns = schema.TABLES[table]["columns"]
    assert outcome_field in columns, f"{table} has no field {outcome_field!r}"
    out = {outcome_field, *(extra or [])}
    if outcome_field in LEAKS.get(table, set()):
        out |= LEAKS[table]
    for name, col in columns.items():
        # a link id (contact_id, deal_id) is one entity, not a pattern: a
        # relation to it says "this one contact", which is not generalisable
        if (col.get("type") in ("Text", "Vector") or name in _TIME_FIELDS
                or name.endswith(_ID_SUFFIXES)):
            out.add(name)
    return sorted(out)


def relate(client: AitoClient, table: str, outcome: dict, where: dict | None = None,
           top_n: int = 10, exclude: list[str] | None = None) -> dict:
    """The field values most related to `outcome` (one proposition, e.g.
    {"reached": True}) in `table`, optionally within the rows matching
    `where`. Ranked by Aito's mutual information; each with its lift, the
    outcome rate with and without the value, and the rows behind it."""
    assert isinstance(outcome, dict) and len(outcome) == 1, \
        f"outcome is one field: value, got {outcome!r}"
    field, value = next(iter(outcome.items()))
    out = set(excluded_fields(table, field, exclude))
    where = where or {}
    relate_on = outcome if not where else {"$on": [outcome, (
        where if len(where) == 1 else {"$and": [{k: v} for k, v in where.items()]})]}
    out |= set(where)          # the population's own conditions explain nothing inside it
    # generous limit: _relate enumerates every field=value, including the
    # excluded ones, and a small window can cut a real relation off
    request = {"from": table, "relate": relate_on, "limit": 300}
    response = client.relate(request)
    rows, population, outcome_rows = [], 0, 0
    for hit in response.get("hits", []):
        r = read_hit(hit, on=bool(where))
        if r is None or r["field"] in out:
            continue
        rows.append({
            "field": r["field"], "value": r["value"],
            "lift": round(hit.get("lift", 0.0), 3),
            "mi": round(hit.get("info", 0.0), 4),
            "rate_with": None if r["rate_with"] is None else round(r["rate_with"], 3),
            "rate_without": None if r["rate_without"] is None else round(r["rate_without"], 3),
            "rows_with": r["rows_with"],
            "thin": r["rows_with"] < THIN,
        })
        population, outcome_rows = r["n"], r["with_outcome"]
    rows.sort(key=lambda r: (-r["mi"], r["field"], str(r["value"])))
    return {
        "table": table, "outcome": outcome, "where": where,
        "population": population, "with_outcome": outcome_rows,
        "relations": rows[:top_n],
        "excluded": sorted(out),
        "note": (f"thin = fewer than {THIN} rows carry the value: a hint, not a finding. "
                 "lift > 1 means the outcome is more common with the value."),
        "request": request,
    }
