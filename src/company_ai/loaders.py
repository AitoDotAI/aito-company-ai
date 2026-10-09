"""CSV -> Aito loaders.

Per CLAUDE.md rule 3, anything surprising in the input raises an
AssertionError carrying the offending row. Loads are idempotent by
drop-and-reload: rerunning a load yields the same table state, never
duplicates. Because touches links to contacts, reloading the rolodex
drops touches first; run load-rolodex before load-touches.
"""

import contextvars
import csv
import re
from datetime import date, datetime
from pathlib import Path

from . import schema
from .aito import AitoClient, AitoError

ROLODEX_FILE = "rolodex.csv"
TOUCHES_FILE = "touches.csv"
SESSIONS_FILE = "sessions.csv"
MATERIALS_FILE = "materials.csv"
CHANNELS_FILE = "channels.csv"
POSTS_FILE = "posts.csv"
TODOS_FILE = "todos.csv"
DEALS_FILE = "deals.csv"
DECISIONS_FILE = "decisions.csv"
EXPERIMENTS_FILE = "experiments.csv"
EVENTS_FILE = "events.csv"
ROUTINES_FILE = "routines.csv"
DOCUMENTS_FILE = "documents.csv"
USERS_FILE = "users.csv"

# the file each table loads from / exports to (export writes a re-loadable CSV)
TABLE_FILES = {
    "contacts": ROLODEX_FILE, "touches": TOUCHES_FILE, "sessions": SESSIONS_FILE,
    "materials": MATERIALS_FILE, "channels": CHANNELS_FILE, "posts": POSTS_FILE,
    "todos": TODOS_FILE, "deals": DEALS_FILE,
    "decisions": DECISIONS_FILE, "experiments": EXPERIMENTS_FILE, "events": EVENTS_FILE,
    "routines": ROUTINES_FILE, "documents": DOCUMENTS_FILE,
    "users": USERS_FILE,
}


# validate.py sets this to a list to COLLECT every failed check in a row rather
# than stop at the first, so one pass over an export shows all of a row's
# problems. Unset (every load path) keeps rule 3 exactly: the first surprise
# raises, with the row attached.
_COLLECT: contextvars.ContextVar = contextvars.ContextVar("_collect", default=None)


def _require(condition: bool, message: str, row: dict) -> None:
    if not condition:
        sink = _COLLECT.get()
        if sink is not None:
            sink.append(message)
            return
        raise AssertionError(f"{message}; offending row: {row}")


def _parse_bool(value: str, field: str, row: dict) -> bool:
    _require(value in ("true", "false"), f"{field} must be 'true' or 'false', got {value!r}", row)
    return value == "true"


def _parse_int(value: str, field: str, row: dict) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        _require(False, f"{field} is not an integer: {value!r}", row)


def _parse_date(value: str, field: str, row: dict) -> str:
    try:
        date.fromisoformat(value)
    except ValueError:
        _require(False, f"{field} is not an ISO date: {value!r}", row)
    return value


DERIVED_CONTACT_COLUMNS = {
    "ever_touched", "ever_reached", "ever_conversation", "ever_meeting",
    "search_title", "search_text", "company_id",
}


def _search_blob(*parts: str) -> str:
    """The searchable text for a row: its identifying words as one analysable
    Text value. The source columns stay categorical String for prediction —
    this is a copy for the v2 search view's `$text` merge (docs/23)."""
    return " ".join(str(p) for p in parts if p)


# The derived search columns (docs/23), factored so both the loader (from CSV)
# and recompute_search (from existing rows) produce identical values — a single
# definition, never drift.
def contact_search_columns(name: str, company: str, role: str, segment: str,
                           tags: str) -> dict:
    return {"search_title": _search_blob(name),
            "search_text": _search_blob(name, company, role, segment, tags)}


def deal_search_columns(company: str, segment: str, stage: str, blocker: str) -> dict:
    return {"search_title": _search_blob(company),
            "search_text": _search_blob(company, segment, stage, blocker)}


def company_slug(name: str) -> str:
    """A stable slug key for a company name — the `companies` entity's id and the
    `company_id` link value on contacts/deals (.ai/tasks/15). Lowercase,
    non-alphanumerics collapsed to '-'. Matches schema.SLUG_PATTERN."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "unknown"


def parse_rolodex_row(row: dict) -> dict:
    expected = set(schema.CONTACTS["columns"]) - DERIVED_CONTACT_COLUMNS
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in expected - {"notes_tags"}:
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["segment"] in schema.SEGMENTS, f"unknown segment {row['segment']!r}", row)
    _require(row["tier"] in schema.TIERS, f"unknown tier {row['tier']!r}", row)
    _require(
        row["ai_lifecycle"] in schema.LIFECYCLES, f"unknown ai_lifecycle {row['ai_lifecycle']!r}", row
    )
    _require(row["source"] in schema.SOURCES, f"unknown source {row['source']!r}", row)
    # tags are ';'-separated in CSV, whitespace-tokenized text in Aito
    tags = " ".join(t for t in row["notes_tags"].split(";") if t)
    return {
        **row,
        "phone_present": _parse_bool(row["phone_present"], "phone_present", row),
        "email_present": _parse_bool(row["email_present"], "email_present", row),
        "notes_tags": tags,
        "created": _parse_date(row["created"], "created", row),
        "company_id": company_slug(row["company"]),   # link to the company entity
        **contact_search_columns(row["name"], row["company"], row["role"],
                                 row["segment"], tags),
    }


DERIVED_TOUCH_COLUMNS = {"days_since_prev_touch", "good_outcome", "reached", "booked"}


def parse_touch_row(row: dict, contact_ids: set[str]) -> dict:
    expected = set(schema.TOUCHES["columns"]) - DERIVED_TOUCH_COLUMNS
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    required = expected - {"next_action", "next_action_due", "notes"}
    for field in required:
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["contact_id"] in contact_ids, f"unknown contact_id {row['contact_id']!r}", row)
    _require(row["window"] in schema.WINDOWS, f"unknown window {row['window']!r}", row)
    _require(row["channel"] in schema.TOUCH_CHANNELS, f"unknown channel {row['channel']!r}", row)
    _require(row["outcome"] in schema.OUTCOMES, f"unknown outcome {row['outcome']!r}", row)
    try:
        ts = datetime.fromisoformat(row["ts"])
    except ValueError:
        _require(False, f"ts is not an ISO datetime: {row['ts']!r}", row)
    actual_weekday = schema.WEEKDAYS[ts.weekday()]
    _require(
        row["weekday"] == actual_weekday,
        f"weekday {row['weekday']!r} does not match ts ({actual_weekday})",
        row,
    )
    _require(
        bool(row["next_action"]) == bool(row["next_action_due"]),
        "next_action and next_action_due must be set together",
        row,
    )
    if row["next_action_due"]:
        _parse_date(row["next_action_due"], "next_action_due", row)
    return {
        **row,
        "next_action": row["next_action"] or None,
        "next_action_due": row["next_action_due"] or None,
        "notes": row["notes"] or None,
        **schema.kpi_flags(row["outcome"]),
    }


def _read_csv(path: Path) -> list[dict]:
    assert path.exists(), f"missing data file: {path}"
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _reload(client: AitoClient, table: str, rows: list[dict]) -> int:
    client.delete_table(table)
    client.create_table(table, schema.TABLES[table])
    client.upload_batch(table, rows)
    loaded = client.count(table)
    assert loaded == len(rows), f"{table}: read {len(rows)} rows but Aito holds {loaded}"
    # Flush, for the same reason update_entries does it — and flush BOTH ENDS
    # of every link this table declares.
    #
    # Link resolution is lazy on this build, and it goes stale in both
    # directions. After `companies` is dropped and recreated, a forward path
    # (company_id.relationship) matches NOTHING until a flush. After `contacts`
    # is reloaded, the reverse index on its TARGET is stale, so
    # $refs.contacts.company_id on a company returns nothing. Neither raises:
    # both look exactly like "no rows match", which is the most expensive way
    # for this to fail. Doing it here means no loader and no caller can forget.
    client.optimize(table)
    for column in schema.TABLES[table]["columns"].values():
        link = column.get("link")
        if link:
            client.optimize(link.split(".")[0])
    return loaded


def create_schema(client: AitoClient) -> dict:
    """Bring the live schema up to the code's definition, non-destructively:
    create missing tables, and add missing columns to existing tables (Aito's
    per-column schema API — no drop, no reload). Extra columns the live table
    has but the code doesn't are reported, never dropped (CLAUDE.md rule 3:
    surprises are information).

    Adding a column does not backfill existing rows — they read null for it
    until (re)loaded. For a column whose value is derived at load time
    (e.g. `won`, `slipped`), reload that table to populate it; for a plain new
    field the values arrive on the next normal load. Returns a report.
    """
    existing = client.get_schema()["schema"]
    created, added, extra, needs_reload = [], {}, {}, {}
    for name, definition in schema.TABLES.items():
        if name not in existing:
            client.create_table(name, definition)
            created.append(name)
            continue
        want = definition["columns"]
        have = existing[name].get("columns", {})
        for column in want:
            if column not in have:
                try:
                    client.add_column(name, column, want[column])
                    added.setdefault(name, []).append(column)
                except AitoError:
                    # a non-nullable column can't be added to a populated table
                    # without a fill value — don't crash; the table needs a reload
                    needs_reload.setdefault(name, []).append(column)
        unknown = sorted(set(have) - set(want))
        if unknown:
            extra[name] = unknown
    return {"created_tables": created, "added_columns": added,
            "extra_columns": extra, "needs_reload": needs_reload}


def derive_contact_funnel(contact_rows: list[dict], data_dir: Path) -> None:
    """Stamp each contact with its furthest sales-funnel stage, from the
    touch outcomes in touches.csv. Read from the file (not Aito) so the
    flags are deterministic from the source and computable before touches
    are loaded. An absent touches.csv means no contact has been touched yet
    — all flags false, which is honest, not a silent skip.

    Note: these flags are a snapshot at load time. Touches logged after a
    load do not retro-update them; rerun load-rolodex to refresh the sales
    funnel. (The website funnel has no such lag — sessions carry their own
    stage flags.)
    """
    touches_path = data_dir / TOUCHES_FILE
    by_contact: dict[str, list[str]] = {}
    if touches_path.exists():
        for t in _read_csv(touches_path):
            by_contact.setdefault(t["contact_id"], []).append(t["outcome"])
    for row in contact_rows:
        row.update(schema.contact_funnel_flags(by_contact.get(row["contact_id"], [])))


# Roles that count as a technical buyer for `companies.technical_contact`.
# Kept next to the harvest because it is a property OF THE HARVEST, not of the
# contact: the generator plants the effect on "we know a CTO there".


def companies_from_csvs(data_dir: Path) -> list[dict]:
    """The distinct companies across the rolodex + deals + documents CSVs — the
    entity rows — each carrying the facts harvested from the rows that link to
    it. `company_id` is the name slug; `name` is the first spelling seen.
    A company may appear as a contact's employer, a deal's account, a document's
    subject, or any mix (.ai/tasks/15) — every source that carries a company is
    scanned so no `company_id` link dangles.

    The facts (industry, relationship, country, mrr_eur, counts) are DERIVED
    here rather than authored: they are summaries of the contacts and deals
    already in the CSVs, so they cannot drift from them. This is load-time
    featurization, the same move as derive_contact_funnel — no prediction
    happens here; predicting *from* these facts is Aito's job (rule 2)."""
    by_id: dict[str, str] = {}
    for filename in (ROLODEX_FILE, DEALS_FILE, DOCUMENTS_FILE):
        path = data_dir / filename
        if path.exists():
            for r in _read_csv(path):
                name = (r.get("company") or "").strip()
                if name:
                    by_id.setdefault(company_slug(name), name)

    contacts = _read_csv(data_dir / ROLODEX_FILE) if (data_dir / ROLODEX_FILE).exists() else []
    deals = _read_csv(data_dir / DEALS_FILE) if (data_dir / DEALS_FILE).exists() else []
    by_company: dict[str, list[dict]] = {}
    deals_by_company: dict[str, list[dict]] = {}
    for r in contacts:
        by_company.setdefault(company_slug((r.get("company") or "").strip()), []).append(r)
    for r in deals:
        deals_by_company.setdefault(company_slug((r.get("company") or "").strip()), []).append(r)

    def _modal(rows: list[dict], field: str) -> str:
        """Most common non-empty value, ties broken alphabetically so the
        harvest is deterministic (the privacy gate diffs these CSVs byte-wise)."""
        counts: dict[str, int] = {}
        for r in rows:
            v = (r.get(field) or "").strip()
            if v:
                counts[v] = counts.get(v, 0) + 1
        if not counts:
            return "unknown"
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    rows = []
    for cid, name in sorted(by_id.items()):
        cds = deals_by_company.get(cid, [])
        ccs = by_company.get(cid, [])
        outcomes = [schema.deal_won(d["stage"]) for d in cds if d.get("stage")]
        if any(o is True for o in outcomes):
            relationship = "customer"
        elif any(o is None for o in outcomes):
            relationship = "prospect"
        elif outcomes:
            relationship = "lost"
        else:
            relationship = "none"
        won_value = sum(int(d.get("value_eur") or 0)
                        for d in cds if schema.deal_won(d.get("stage", "")) is True)
        rows.append({
            "company_id": cid,
            "name": name,
            # a company's industry is whatever its people and deals say it is
            "industry": _modal(ccs or cds, "segment"),
            "relationship": relationship,
            "country": _modal(ccs, "country"),
            "mrr_eur": won_value // 12,
            "open_deals": sum(1 for d in cds
                              if schema.deal_won(d.get("stage", "")) is None),
            "contact_count": len(ccs),
            # companies <- contacts, walked at load time
            "technical_contact": any(r.get("role") in schema.TECHNICAL_ROLES
                                     for r in ccs),
        })
    return rows


def load_companies(client: AitoClient, data_dir: Path) -> int:
    """(Re)load the companies entity from the distinct companies in the rolodex +
    deals CSVs. Load this BEFORE contacts/deals — it is their `company_id` link
    target, and Aito refuses to drop a table that is linked into, so the reload
    order is companies-first on a fresh load (.ai/tasks/15)."""
    return _reload(client, "companies", companies_from_csvs(data_dir))


def load_rolodex(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / ROLODEX_FILE)
    rows = [parse_rolodex_row(r) for r in raw]
    ids = [r["contact_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate contact_id in rolodex"
    derive_contact_funnel(rows, data_dir)
    # touches links to contacts, so contacts cannot be dropped under it
    client.delete_table("touches")
    return _reload(client, "contacts", rows)


def derive_recency(rows: list[dict]) -> None:
    """Stamp each touch with the contact's recency state when it happened.

    This is the days_since_last_touch feature of docs/03 query 1, bucketed
    by queries.bucket_days_since; 'first' marks a never-before-touched
    contact. Derived deterministically from the data itself, in place.
    """
    from .queries import bucket_days_since

    previous: dict[str, date] = {}
    for row in sorted(rows, key=lambda r: (r["ts"], r["touch_id"])):
        day = datetime.fromisoformat(row["ts"]).date()
        prev = previous.get(row["contact_id"])
        row["days_since_prev_touch"] = bucket_days_since(
            (day - prev).days if prev else None
        )
        previous[row["contact_id"]] = day


def load_touches(client: AitoClient, data_dir: Path) -> int:
    contact_ids = {r["contact_id"] for r in _read_csv(data_dir / ROLODEX_FILE)}
    raw = _read_csv(data_dir / TOUCHES_FILE)
    rows = [parse_touch_row(r, contact_ids) for r in raw]
    ids = [r["touch_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate touch_id in touches"
    derive_recency(rows)
    return _reload(client, "touches", rows)


def parse_session_row(row: dict) -> dict:
    expected = set(schema.SESSIONS["columns"])
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in expected - {"campaign"}:
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["source"] in schema.WEB_SOURCES, f"unknown source {row['source']!r}", row)
    _require(row["device"] in schema.DEVICES, f"unknown device {row['device']!r}", row)
    _require(
        row["landing_page"] in schema.LANDING_PAGES,
        f"unknown landing_page {row['landing_page']!r}", row,
    )
    _parse_date(row["ts"], "ts", row)
    flags = {k: _parse_bool(row[k], k, row)
             for k in ("signed_up", "started_trial", "converted_paid")}
    # the funnel is monotone: paid implies trial implies signup
    _require(
        not flags["converted_paid"] or flags["started_trial"],
        "converted_paid is true but started_trial is false", row,
    )
    _require(
        not flags["started_trial"] or flags["signed_up"],
        "started_trial is true but signed_up is false", row,
    )
    return {**row, **flags, "campaign": row["campaign"] or None}


def load_sessions(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / SESSIONS_FILE)
    rows = [parse_session_row(r) for r in raw]
    ids = [r["session_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate session_id in sessions"
    return _reload(client, "sessions", rows)


# weekday, length_bucket, and won are derived at load, never in the CSV
def parse_material_row(row: dict) -> dict:
    expected = set(schema.MATERIALS["columns"])
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in ("material_id", "type", "title", "topic", "lane", "ai_made", "created"):
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["type"] in schema.MATERIAL_TYPES, f"unknown material type {row['type']!r}", row)
    _require(row["lane"] in schema.LANES, f"unknown lane {row['lane']!r}", row)
    _require(row["ai_made"] in schema.AI_MADE, f"unknown ai_made {row['ai_made']!r}", row)
    _require(row["topic"] in schema.POST_TOPICS, f"unknown topic {row['topic']!r}", row)
    _parse_date(row["created"], "created", row)
    return {**row, "length_chars": _parse_int(row["length_chars"], "length_chars", row)}


def load_materials(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / MATERIALS_FILE)
    rows = [parse_material_row(r) for r in raw]
    ids = [r["material_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate material_id in materials"
    return _reload(client, "materials", rows)


def parse_channel_row(row: dict) -> dict:
    expected = set(schema.CHANNELS["columns"])
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in ("channel_id", "name", "platform", "created"):
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["platform"] in schema.PLATFORMS, f"unknown platform {row['platform']!r}", row)
    _parse_date(row["created"], "created", row)
    return {**row}


def load_channels(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / CHANNELS_FILE)
    rows = [parse_channel_row(r) for r in raw]
    ids = [r["channel_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate channel_id in channels"
    return _reload(client, "channels", rows)


# input columns of a post (the rest are denormalized from material/channel or derived)
DERIVED_POST_COLUMNS = {"weekday", "length_bucket", "won", "platform", "ai_made",
                        "lane", "topic", "length_chars"}


def parse_post_row(row: dict, materials: dict, channels: dict) -> dict:
    """A material posted/planned to a channel. The material's and channel's
    attributes are denormalized onto the row so the scorer's predict is one
    query. `materials`/`channels` map id -> row (loaded first)."""
    expected = set(schema.POSTS["columns"]) - DERIVED_POST_COLUMNS
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in ("post_id", "material_id", "channel_id", "status", "tone",
                  "format", "link_placement"):
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["status"] in schema.POST_STATUS, f"unknown status {row['status']!r}", row)
    _require(row["tone"] in schema.TONES, f"unknown tone {row['tone']!r}", row)
    _require(row["format"] in schema.POST_FORMATS, f"unknown format {row['format']!r}", row)
    _require(row["link_placement"] in schema.LINK_PLACEMENTS,
             f"unknown link_placement {row['link_placement']!r}", row)
    _require(row["material_id"] in materials, f"unknown material_id {row['material_id']!r}", row)
    _require(row["channel_id"] in channels, f"unknown channel_id {row['channel_id']!r}", row)
    material, channel = materials[row["material_id"]], channels[row["channel_id"]]

    posted = row["status"] == "posted"
    outcome = row["outcome"] or None
    if outcome:
        _require(outcome in schema.POST_OUTCOMES, f"unknown outcome {outcome!r}", row)
    # KPIs and posted_at belong to a posted post; an unposted one must not claim them
    _require(posted == bool(row["posted_at"]),
             f"status {row['status']!r} and posted_at {row['posted_at']!r} disagree", row)
    weekday = None
    if row["posted_at"]:
        _parse_date(row["posted_at"][:10], "posted_at", row)
        weekday = schema.WEEKDAYS[datetime.fromisoformat(row["posted_at"][:10]).weekday()]
    length = material["length_chars"]
    return {
        "post_id": row["post_id"], "material_id": row["material_id"],
        "channel_id": row["channel_id"], "status": row["status"],
        "posted_at": row["posted_at"] or None, "weekday": weekday,
        "tone": row["tone"], "format": row["format"],
        "link_placement": row["link_placement"],
        "reach_or_views": _parse_int(row["reach_or_views"], "reach_or_views", row) if row["reach_or_views"] else None,
        "upvotes": _parse_int(row["upvotes"], "upvotes", row) if row["upvotes"] else None,
        "trials": _parse_int(row["trials"], "trials", row) if row["trials"] else None,
        "outcome": outcome,
        # denormalized from material/channel + derived:
        "platform": channel["platform"], "ai_made": material["ai_made"],
        "lane": material["lane"], "topic": material["topic"],
        "length_chars": length, "length_bucket": schema.post_length_bucket(length),
        "won": schema.post_won(row["status"], outcome),
    }


def load_posts(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / POSTS_FILE)
    # posts denormalize from materials + channels; they must be loaded first.
    materials = {m["material_id"]: m for m in client.query({"from": "materials", "limit": 100000})["hits"]}
    channels = {c["channel_id"]: c for c in client.query({"from": "channels", "limit": 100000})["hits"]}
    rows = [parse_post_row(r, materials, channels) for r in raw]
    ids = [r["post_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate post_id in posts"
    return _reload(client, "posts", rows)


# set only by the app, never from CSV: sort_order by drag-reorder, rev by
# every row write (log._write_todo)
DERIVED_TODO_COLUMNS = {"sort_order", "rev", "revs"}


def parse_todo_row(row: dict, contact_ids: set[str] | None = None,
                   deal_ids: set[str] | None = None) -> dict:
    expected = set(schema.TODOS["columns"]) - DERIVED_TODO_COLUMNS
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in ("todo_id", "area", "title", "status", "priority", "prep_status"):
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["area"] in schema.TODO_AREAS, f"unknown area {row['area']!r}", row)
    _require(row["status"] in schema.TODO_STATUS, f"unknown status {row['status']!r}", row)
    _require(row["prep_status"] in schema.PREP_STATUS,
             f"unknown prep_status {row['prep_status']!r}", row)
    if row["action_type"]:
        _require(row["action_type"] in schema.ACTION_TYPES,
                 f"unknown action_type {row['action_type']!r}", row)
    priority = _parse_int(row["priority"], "priority", row)
    _require(priority >= 1, f"priority must be >= 1, got {priority}", row)
    if row["linked_type"]:
        _require(row["linked_type"] in schema.LINKED_TYPES,
                 f"unknown linked_type {row['linked_type']!r}", row)
    # work routing. Shape-checked, not enum-checked (schema.SLUG_PATTERN): which
    # agent lanes and instances exist is deployment-specific.
    for field in ("role", "owner"):
        if row[field]:
            _require(re.fullmatch(schema.SLUG_PATTERN, row[field]) is not None,
                     f"{field} must be a lowercase slug, got {row[field]!r}", row)
    # link existence, when the caller supplies the known-id sets (live writes
    # and load_todos do; bare unit calls skip it). A dangling link is a
    # surprise, not a default (rule 3).
    if deal_ids is not None and row["linked_type"] == "deal" and row["linked_id"]:
        _require(row["linked_id"] in deal_ids, f"unknown deal linked_id {row['linked_id']!r}", row)
    if contact_ids is not None and row["stakeholder_id"]:
        _require(row["stakeholder_id"] in contact_ids,
                 f"unknown stakeholder_id {row['stakeholder_id']!r}", row)
    # the lens invariant applies to the OPEN worklist: calendar areas require a
    # due_date, deadline areas (operations) allow one optionally, the rest
    # forbid it. Terminal todos (done/archived) are exempt — off the worklist.
    if row["status"] not in schema.TERMINAL_STATUSES:
        if row["area"] in schema.CALENDAR_AREAS:
            _require(bool(row["due_date"]), f"open {row['area']} todo needs a due_date", row)
        elif row["area"] not in schema.DEADLINE_AREAS:
            _require(not row["due_date"], f"open {row['area']} todo must not have a due_date", row)
    if row["due_date"]:
        _parse_date(row["due_date"], "due_date", row)
    if row["slot"]:
        _require(re.fullmatch(r"[0-2]\d:[0-5]\d", row["slot"]) is not None,
                 f"slot must be HH:MM clock time, got {row['slot']!r}", row)
    # slipped is set only on done todos; open todos have no meaningful value.
    # (v2 coerces a nullable Boolean's null to False — docs/24 — so a round-
    # tripped open todo carries slipped=false; ignore it unless the todo is done.)
    slipped = None
    if row["status"] == "done" and row["slipped"]:
        slipped = _parse_bool(row["slipped"], "slipped", row)
    return {
        **row,
        "priority": priority,
        "detail": row["detail"] or None,
        "action_type": row["action_type"] or None,
        "due_date": row["due_date"] or None,
        "window": row["window"] or None,
        "slot": row["slot"] or None,
        "sort_order": None,  # unset until dragged
        "rev": "rv-0",  # the initial version (log.INITIAL_REV); bumped by every row write
        "revs": "rv-0",
        "linked_id": row["linked_id"] or None,
        "linked_type": row["linked_type"] or None,
        "stakeholder_id": row["stakeholder_id"] or None,
        "slipped": slipped,
        "role": row["role"] or None,
        "owner": row["owner"] or None,
    }


def load_todos(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / TODOS_FILE)
    # row well-formedness only (enums, formats). Cross-table link existence is
    # NOT checked here: todos can load before deals/contacts, so a live fetch
    # would be order-dependent. The generator guarantees valid links; the live
    # write path (add_todo/update_todo) validates user-supplied links.
    rows = [parse_todo_row(r) for r in raw]
    ids = [r["todo_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate todo_id in todos"
    return _reload(client, "todos", rows)


def clear_table(client: AitoClient, table: str) -> int:
    """Empty a table back to a clean, schema-correct empty state (drop +
    recreate). For 'real data in, leave the rest honestly empty' without a
    one-off script. Returns the row count after (0)."""
    assert table in schema.TABLES, f"unknown table {table!r}; have {sorted(schema.TABLES)}"
    client.delete_table(table)
    client.create_table(table, schema.TABLES[table])
    after = client.count(table)
    assert after == 0, f"{table}: expected empty after clear, holds {after}"
    return after


DERIVED_DECISION_COLUMNS = {"confidence_bucket", "accepted"}


def parse_decision_row(row: dict) -> dict:
    expected = set(schema.DECISIONS["columns"]) - DERIVED_DECISION_COLUMNS
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in ("decision_id", "ts", "decision_type", "chosen",
                  "agent_confidence", "human_action"):
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["decision_type"] in schema.DECISION_TYPES,
             f"unknown decision_type {row['decision_type']!r}", row)
    _require(row["human_action"] in schema.HUMAN_ACTIONS,
             f"unknown human_action {row['human_action']!r}", row)
    try:
        conf = float(row["agent_confidence"])
    except ValueError:
        _require(False, f"agent_confidence not a number: {row['agent_confidence']!r}", row)
    _require(0.0 <= conf <= 1.0, f"agent_confidence out of [0,1]: {conf}", row)
    return {
        **row,
        "agent_confidence": conf,
        "human_alternative": row["human_alternative"] or None,
        "outcome_after": row["outcome_after"] or None,
        "confidence_bucket": schema.confidence_bucket(conf),
        "accepted": row["human_action"] == "accepted",
    }


def load_decisions(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / DECISIONS_FILE)
    rows = [parse_decision_row(r) for r in raw]
    ids = [r["decision_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate decision_id in decisions"
    return _reload(client, "decisions", rows)


DERIVED_EXPERIMENT_COLUMNS = {"validated"}


def parse_experiment_row(row: dict) -> dict:
    expected = set(schema.EXPERIMENTS["columns"]) - DERIVED_EXPERIMENT_COLUMNS
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in ("experiment_id", "created", "area", "type", "hypothesis",
                  "metric", "baseline", "target", "effort", "status", "started"):
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["area"] in schema.EXPERIMENT_AREAS, f"unknown area {row['area']!r}", row)
    _require(row["type"] in schema.EXPERIMENT_TYPES, f"unknown type {row['type']!r}", row)
    _require(row["effort"] in schema.EXPERIMENT_EFFORTS, f"unknown effort {row['effort']!r}", row)
    _require(row["status"] in schema.EXPERIMENT_STATUS, f"unknown status {row['status']!r}", row)
    try:
        baseline, target = float(row["baseline"]), float(row["target"])
        result = float(row["result"]) if row["result"] else None
    except ValueError:
        _require(False, f"baseline/target/result not numeric: {row}", row)
    # a verdict needs a measured result; an unfinished bet must not claim one
    terminal = row["status"] in schema.EXPERIMENT_TERMINAL
    _require(terminal == (result is not None),
             f"status {row['status']!r} and result {row['result']!r} disagree "
             "(a verdict needs a result; running/abandoned must not have one)", row)
    return {
        **row,
        "baseline": baseline, "target": target, "result": result,
        "learning": row["learning"] or None,
        "decided": row["decided"] or None,
        "validated": schema.experiment_validated(row["status"]),
    }


def load_experiments(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / EXPERIMENTS_FILE)
    rows = [parse_experiment_row(r) for r in raw]
    ids = [r["experiment_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate experiment_id in experiments"
    return _reload(client, "experiments", rows)


def parse_event_row(row: dict) -> dict:
    expected = set(schema.EVENTS["columns"])
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in ("event_id", "name", "type", "starts", "status", "created"):
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["type"] in schema.EVENT_TYPES, f"unknown event type {row['type']!r}", row)
    _require(row["status"] in schema.EVENT_STATUS, f"unknown status {row['status']!r}", row)
    _parse_date(row["starts"], "starts", row)
    _parse_date(row["created"], "created", row)
    outcome = row["outcome"] or None
    if outcome:
        _require(outcome in schema.EVENT_OUTCOMES, f"unknown outcome {outcome!r}", row)
    # an outcome is graded only after attending; a non-attended event must not claim one
    _require((row["status"] == "attended") or outcome is None,
             f"outcome {outcome!r} only valid on an attended event (status={row['status']!r})", row)
    return {
        **row,
        "location": row["location"] or None,
        "cost_eur": _parse_int(row["cost_eur"], "cost_eur", row) if row["cost_eur"] else None,
        "decided": row["decided"] or None,
        "outcome": outcome,
        "notes": row["notes"] or None,
    }


def load_events(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / EVENTS_FILE)
    rows = [parse_event_row(r) for r in raw]
    ids = [r["event_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate event_id in events"
    return _reload(client, "events", rows)


def parse_routine_row(row: dict) -> dict:
    expected = set(schema.ROUTINES["columns"])
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in ("routine_id", "title", "area", "cadence", "prep", "created"):
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["area"] in schema.TODO_AREAS, f"unknown area {row['area']!r}", row)
    _require(row["cadence"] in schema.ROUTINE_CADENCE, f"unknown cadence {row['cadence']!r}", row)
    _require(row["prep"] in schema.ROUTINE_PREP, f"unknown prep {row['prep']!r}", row)
    if row["cadence"] == "weekly":
        _require(row["weekday"] in schema.WEEKDAYS, f"weekly routine needs a weekday, got {row['weekday']!r}", row)
    dom = None
    if row["cadence"] == "monthly":
        dom = _parse_int(row["day_of_month"], "day_of_month", row)
        _require(1 <= dom <= 28, f"day_of_month must be 1-28, got {dom}", row)
    if row["last_done"]:
        _parse_date(row["last_done"], "last_done", row)
    _parse_date(row["created"], "created", row)
    return {
        **row,
        "weekday": row["weekday"] or None,
        "day_of_month": dom,
        "prompt": row["prompt"] or None,
        "last_done": row["last_done"] or None,
        "active": _parse_bool(row["active"], "active", row),
        "notes": row["notes"] or None,
    }


def load_routines(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / ROUTINES_FILE)
    rows = [parse_routine_row(r) for r in raw]
    ids = [r["routine_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate routine_id in routines"
    return _reload(client, "routines", rows)


DERIVED_DOCUMENT_COLUMNS = {"company_id"}


def parse_document_row(row: dict) -> dict:
    expected = set(schema.DOCUMENTS["columns"]) - DERIVED_DOCUMENT_COLUMNS
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in ("doc_id", "title", "body", "kind", "created", "updated"):
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["kind"] in schema.DOC_KINDS, f"unknown kind {row['kind']!r}", row)
    _require(not row["area"] or row["area"] in schema.DOCUMENT_AREAS,
             f"unknown area {row['area']!r}", row)
    _parse_date(row["created"], "created", row)
    _parse_date(row["updated"], "updated", row)
    if row["noted_on"]:
        _parse_date(row["noted_on"], "noted_on", row)   # the diary date, when set
    company = row["company"] or None
    return {
        **row,
        "area": row["area"] or None,
        "topics": row["topics"] or None,
        "noted_on": row["noted_on"] or None,
        "company": company,
        "company_id": company_slug(company) if company else None,  # link to the entity
        "stakeholder_id": row["stakeholder_id"] or None,
        "source": row["source"] or None,
    }


def load_documents(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / DOCUMENTS_FILE)
    rows = [parse_document_row(r) for r in raw]
    ids = [r["doc_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate doc_id in documents"
    return _reload(client, "documents", rows)


def parse_user_row(row: dict) -> dict:
    expected = set(schema.USERS["columns"])
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in ("user_id", "name", "email", "role", "created"):
        _require(bool(row[field]), f"{field} is empty", row)
    _require(row["role"] in schema.USER_ROLES, f"unknown role {row['role']!r}", row)
    return {
        **row,
        "email": row["email"].strip().lower(),   # matched against the Easy Auth identity
        "active": _parse_bool(row["active"], "active", row),
        "created": _parse_date(row["created"], "created", row),
    }


def load_users(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / USERS_FILE)
    rows = [parse_user_row(r) for r in raw]
    ids = [r["user_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate user_id in users"
    emails = [r["email"] for r in rows]
    assert len(emails) == len(set(emails)), "duplicate email in users"
    return _reload(client, "users", rows)


def export_table(client: AitoClient, table: str, out_dir: Path) -> tuple[Path, int]:
    """Dump a table to a re-loadable CSV (Aito → files, the backup half of
    Plane B). Writes the loader's *input* columns only — derived columns are
    dropped and the notes_tags transform is reversed — so the file loads back
    through `load-<table>` cleanly. Written to out_dir/<table's load file>."""
    assert table in TABLE_FILES, f"unknown table {table!r}; have {sorted(TABLE_FILES)}"
    derived = {
        "contacts": DERIVED_CONTACT_COLUMNS,
        "touches": DERIVED_TOUCH_COLUMNS,
        "posts": DERIVED_POST_COLUMNS,
        "deals": DERIVED_DEAL_COLUMNS,
        "todos": DERIVED_TODO_COLUMNS,
        "decisions": DERIVED_DECISION_COLUMNS,
        "experiments": DERIVED_EXPERIMENT_COLUMNS,
        "documents": DERIVED_DOCUMENT_COLUMNS,
    }.get(table, set())
    columns = [c for c in schema.TABLES[table]["columns"] if c not in derived]
    rows = client.query({"from": table, "limit": 100000})["hits"]
    rows.sort(key=lambda r: str(r.get(columns[0], "")))

    def fmt(col: str, value) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if col == "notes_tags":  # Aito stores space-joined; CSV input is ';'-joined
            return str(value).replace(" ", ";")
        return str(value)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / TABLE_FILES[table]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: fmt(c, row.get(c)) for c in columns})
    return path, len(rows)


DERIVED_DEAL_COLUMNS = {"won", "search_title", "search_text", "company_id"}


def parse_deal_row(row: dict) -> dict:
    # won derived from stage; search_* derived for the search view
    expected = set(schema.DEALS["columns"]) - DERIVED_DEAL_COLUMNS
    _require(set(row) == expected, f"unexpected columns {sorted(set(row) ^ expected)}", row)
    for field in expected:
        _require(bool(row[field]) or row[field] == "0", f"{field} is empty", row)
    _require(row["segment"] in schema.SEGMENTS, f"unknown segment {row['segment']!r}", row)
    _require(row["stage"] in schema.DEAL_STAGES, f"unknown stage {row['stage']!r}", row)
    _require(row["blocker"] in schema.DEAL_BLOCKERS, f"unknown blocker {row['blocker']!r}", row)
    probability = _parse_int(row["probability"], "probability", row)
    _require(0 <= probability <= 100, f"probability out of 0-100: {probability}", row)
    _parse_date(row["last_touch_date"], "last_touch_date", row)
    _parse_date(row["created"], "created", row)
    return {
        **row,
        "value_eur": _parse_int(row["value_eur"], "value_eur", row),
        "probability": probability,
        "champion_present": _parse_bool(row["champion_present"], "champion_present", row),
        "won": schema.deal_won(row["stage"]),  # true/false/None
        "company_id": company_slug(row["company"]),   # link to the company entity
        **deal_search_columns(row["company"], row["segment"], row["stage"], row["blocker"]),
    }


def load_deals(client: AitoClient, data_dir: Path) -> int:
    raw = _read_csv(data_dir / DEALS_FILE)
    rows = [parse_deal_row(r) for r in raw]
    ids = [r["deal_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate deal_id in deals"
    return _reload(client, "deals", rows)


# table -> its loader, and the order to load in (contacts before touches, which
# load_rolodex drops). Used by load_all and the migration recipe.
LOADERS = {
    "contacts": load_rolodex, "touches": load_touches, "sessions": load_sessions,
    "materials": load_materials, "channels": load_channels, "posts": load_posts,
    "deals": load_deals, "todos": load_todos,
    "decisions": load_decisions, "experiments": load_experiments, "events": load_events,
    "routines": load_routines, "documents": load_documents,
    "users": load_users,
}
LOAD_ORDER = ["users", "contacts", "touches", "sessions", "materials", "channels",
              "posts", "deals", "todos", "decisions", "experiments", "events",
              "routines", "documents"]


def diagnose(client: AitoClient) -> dict:
    """Read-only health report for an instance: its build, and how its schema
    compares to what the code expects (missing/extra tables and columns, plus
    row counts). The basis for `company-ai doctor` — it answers "is this
    instance behind?" without guessing. Writes nothing."""
    build = client.version()
    live = client.get_schema()["schema"]
    tables, missing_tables = [], []
    for name, definition in schema.TABLES.items():
        if name not in live:
            missing_tables.append(name)
            tables.append({"name": name, "present": False, "rows": None,
                           "missing_columns": list(definition["columns"]),
                           "extra_columns": [], "mismatched_columns": []})
            continue
        live_cols = live[name].get("columns", {})
        want, have = set(definition["columns"]), set(live_cols)
        # type/analyzer drift on columns that exist in both: Aito can't alter
        # these in place (it's a recreate+reload migration), so a name-only
        # check would call a silently-wrong analyzer "clean". Compare type, and
        # analyzer where the code pins one.
        mismatched = []
        for col in sorted(want & have):
            want_def, have_def = definition["columns"][col], live_cols[col]
            if want_def["type"] != have_def.get("type"):
                mismatched.append({"column": col, "field": "type",
                                   "want": want_def["type"], "have": have_def.get("type")})
            elif want_def.get("analyzer") and want_def["analyzer"] != have_def.get("analyzer"):
                mismatched.append({"column": col, "field": "analyzer",
                                   "want": want_def["analyzer"], "have": have_def.get("analyzer")})
        tables.append({"name": name, "present": True, "rows": client.count(name),
                       "missing_columns": sorted(want - have),
                       "extra_columns": sorted(have - want),
                       "mismatched_columns": mismatched})
    drift = (bool(missing_tables)
             or any(t.get("missing_columns") or t.get("mismatched_columns")
                    for t in tables if t["present"]))
    return {
        "build": build,
        "tables": tables,
        "missing_tables": missing_tables,
        "extra_tables": sorted(set(live) - set(schema.TABLES)),
        "schema_drift": drift,
    }


def export_all(client: AitoClient, out_dir: Path) -> list[tuple[str, int]]:
    """Dump every table the instance has to re-loadable CSVs in out_dir — the
    first step of an instance->instance migration. Skips tables not present."""
    live = client.get_schema()["schema"]
    done = []
    for table in schema.TABLES:
        # a non-CSV config table (no seed file) is skipped here.
        if table in live and table in TABLE_FILES:
            _, n = export_table(client, table, out_dir)
            done.append((table, n))
    return done


def load_all(client: AitoClient, data_dir: Path) -> list[tuple[str, int]]:
    """Load every table whose CSV is present in data_dir, in dependency order
    (contacts before touches). The second step of a migration, after
    create_schema on the target instance.

    Validates the WHOLE directory first (validate.py) and writes nothing if any
    row fails — the same all-or-nothing as before, but the refusal lists every
    problem at once instead of the first one."""
    from . import validate
    report = validate.validate_dir(data_dir)
    if not report.ok:
        raise validate.DataProblems(f"{data_dir} does not load:\n{report.render()}")
    done = []
    # companies has no CSV of its own — it is derived from the distinct companies
    # in the rolodex + deals + documents CSVs (.ai/tasks/15). It is the
    # `company_id` link target, so it loads FIRST, before contacts/deals/documents.
    if any((data_dir / f).exists() for f in (ROLODEX_FILE, DEALS_FILE, DOCUMENTS_FILE)):
        done.append(("companies", load_companies(client, data_dir)))
    for table in LOAD_ORDER:
        if (data_dir / TABLE_FILES[table]).exists():
            done.append((table, LOADERS[table](client, data_dir)))
    return done
