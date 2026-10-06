"""Check a whole data directory before any of it is loaded.

Rule 3 makes every loader raise on the first surprising row, with the row
attached. That is right for a pipeline that should never half-load, and brutal
for someone bringing their own data for the first time: fix one row, rerun,
hit the next, repeat three hundred times. Most of those three hundred are the
SAME problem — usually one segment name the deployment has not declared yet.

So this runs every parser over every row of every CSV present, collects the
failures instead of stopping at the first, and groups them by message: "unknown
segment 'public-sector' — 312 rows (lines 2, 3, 5, …)" is one fix, not 312.
It needs no Aito instance — only the files and the configured vocabulary
(docs/32) — so a newcomer can check their export before touching anything.

Nothing is relaxed. `load_all` runs this first and still refuses to write a
single row if anything fails; the difference is that the refusal now lists
everything at once.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import loaders, schema

# which column holds the identity of each table (duplicates are an error)
ID_COLUMNS = {
    "users": "user_id", "contacts": "contact_id", "touches": "touch_id",
    "sessions": "session_id", "materials": "material_id", "channels": "channel_id",
    "posts": "post_id", "deals": "deal_id", "todos": "todo_id",
    "decisions": "decision_id", "experiments": "experiment_id", "events": "event_id",
    "routines": "routine_id", "documents": "doc_id",
}

# "unknown <field> 'x'" -> the schema set it was checked against. Keyed by
# (table, field) where the same field name means different vocabularies in
# different tables (a contact's `source` is not a session's `source`).
_SET_FOR = {
    ("contacts", "segment"): "SEGMENTS", ("contacts", "tier"): "TIERS",
    ("contacts", "source"): "SOURCES", ("contacts", "ai_lifecycle"): "LIFECYCLES",
    ("touches", "channel"): "TOUCH_CHANNELS", ("touches", "outcome"): "OUTCOMES",
    ("touches", "window"): "WINDOWS",
    ("sessions", "source"): "WEB_SOURCES", ("sessions", "device"): "DEVICES",
    ("deals", "segment"): "SEGMENTS", ("deals", "stage"): "DEAL_STAGES",
    ("deals", "blocker"): "DEAL_BLOCKERS",
    ("materials", "material"): "MATERIAL_TYPES",
    ("channels", "platform"): "PLATFORMS",
    ("posts", "tone"): "TONES", ("posts", "format"): "POST_FORMATS",
    ("posts", "topic"): "POST_TOPICS", ("posts", "status"): "POST_STATUS",
    ("posts", "outcome"): "POST_OUTCOMES", ("posts", "lane"): "LANES",
    ("todos", "area"): "TODO_AREAS", ("todos", "status"): "TODO_STATUS",
    ("events", "event"): "EVENT_TYPES", ("events", "status"): "EVENT_STATUS",
    ("events", "outcome"): "EVENT_OUTCOMES",
    ("experiments", "area"): "EXPERIMENT_AREAS", ("experiments", "status"): "EXPERIMENT_STATUS",
    ("experiments", "type"): "EXPERIMENT_TYPES", ("experiments", "effort"): "EXPERIMENT_EFFORTS",
    ("routines", "cadence"): "ROUTINE_CADENCE", ("routines", "prep"): "ROUTINE_PREP",
    ("documents", "kind"): "DOC_KINDS", ("users", "role"): "USER_ROLES",
}
_UNKNOWN = re.compile(r"^unknown (\w+) '(.*)'$")


@dataclass
class Problem:
    table: str
    message: str           # the parser's message, without the row dump
    lines: list[int] = field(default_factory=list)   # 1-based CSV lines (header = 1)

    def hint(self) -> str:
        """For an unknown value: what IS allowed, and whether it is yours to change."""
        m = _UNKNOWN.match(self.message)
        if not m:
            return ""
        name = _SET_FOR.get((self.table, m.group(1)))
        if not name:
            return ""
        allowed = ", ".join(sorted(getattr(schema, name)))
        if name in schema.OVERRIDABLE:
            return (f"allowed: {allowed} — or add it to {name} in your vocabulary "
                    f"file (COMPANY_AI_VOCABULARY, docs/32)")
        return f"allowed: {allowed} — {name} is fixed: the code reads these values"


@dataclass
class Report:
    checked: dict[str, int] = field(default_factory=dict)   # table -> rows read
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def bad_rows(self) -> int:
        return sum(len(p.lines) for p in self.problems)

    def render(self, max_lines: int = 8) -> str:
        out = []
        for table, n in self.checked.items():
            mine = [p for p in self.problems if p.table == table]
            out.append(f"{loaders.TABLE_FILES[table]:16} {n:6} rows  "
                       + ("ok" if not mine else f"{sum(len(p.lines) for p in mine)} problem(s)"))
            for p in sorted(mine, key=lambda p: -len(p.lines)):
                shown = ", ".join(map(str, p.lines[:max_lines]))
                more = f", … +{len(p.lines) - max_lines} more" if len(p.lines) > max_lines else ""
                count = f"{len(p.lines)} row" + ("s" if len(p.lines) != 1 else "")
                out.append(f"    {p.message}  ({count}: line {shown}{more})")
                if p.hint():
                    out.append(f"      → {p.hint()}")
        if not self.checked:
            out.append("no CSVs found")
        out.append("")
        out.append("OK — nothing to fix" if self.ok else
                   f"{len(self.problems)} distinct problem(s) across {self.bad_rows} row(s); "
                   "nothing was loaded")
        return "\n".join(out)


def _strip_row(message: str) -> str:
    """The parser appends '; offending row: {...}'. In a grouped report the line
    number points at the row, and the dump would make identical problems unique."""
    return message.split("; offending row:")[0]


def validate_dir(data_dir: Path) -> Report:
    """Parse every row of every CSV present in `data_dir`, collecting failures."""
    data_dir = Path(data_dir)
    report = Report()
    grouped: dict[tuple[str, str], Problem] = {}

    def fail(table: str, line: int, message: str) -> None:
        key = (table, message)
        if key not in grouped:
            grouped[key] = Problem(table, message)
            report.problems.append(grouped[key])
        grouped[key].lines.append(line)

    # cross-table context, built from the files rather than from an instance
    def raw(table: str) -> list[dict]:
        path = data_dir / loaders.TABLE_FILES[table]
        return loaders._read_csv(path) if path.exists() else []

    contact_ids = {r.get("contact_id") for r in raw("contacts")}
    parsed_by_id: dict[str, dict] = {"materials": {}, "channels": {}}

    def parse(table: str, row: dict) -> dict:
        if table == "touches":
            return loaders.parse_touch_row(row, contact_ids)
        if table == "posts":
            return loaders.parse_post_row(row, parsed_by_id["materials"], parsed_by_id["channels"])
        return {
            "users": loaders.parse_user_row, "contacts": loaders.parse_rolodex_row,
            "sessions": loaders.parse_session_row, "materials": loaders.parse_material_row,
            "channels": loaders.parse_channel_row, "deals": loaders.parse_deal_row,
            "todos": loaders.parse_todo_row, "decisions": loaders.parse_decision_row,
            "experiments": loaders.parse_experiment_row, "events": loaders.parse_event_row,
            "routines": loaders.parse_routine_row, "documents": loaders.parse_document_row,
        }[table](row)

    for table in loaders.LOAD_ORDER:        # materials/channels before posts
        path = data_dir / loaders.TABLE_FILES[table]
        if not path.exists():
            continue
        rows = loaders._read_csv(path)
        report.checked[table] = len(rows)
        seen: dict[str, int] = {}
        for i, row in enumerate(rows, start=2):           # line 1 is the header
            # collect EVERY failed check in the row, not just the first. A check
            # that fails can leave later code reading a bad value; any exception
            # after a recorded failure is that cascade, so it is not reported.
            sink: list[str] = []
            token = loaders._COLLECT.set(sink)
            parsed = None
            try:
                parsed = parse(table, dict(row))
            except Exception as e:                        # noqa: BLE001 — reported below
                if not sink:
                    sink.append(f"missing column {e}" if isinstance(e, KeyError)
                                else _strip_row(str(e)))
            finally:
                loaders._COLLECT.reset(token)
            for message in sink:
                fail(table, i, message)
            # duplicates are checked on the raw id, so a bad row cannot hide one
            ident = row.get(ID_COLUMNS[table])
            if ident in seen:
                fail(table, i, f"duplicate {ID_COLUMNS[table]} {ident!r} (first on line {seen[ident]})")
            elif ident:
                seen[ident] = i
            if parsed is not None and not sink and table in parsed_by_id:
                parsed_by_id[table][ident] = parsed
    return report


class DataProblems(AssertionError):
    """Raised by load_all when the directory does not validate. Subclasses
    AssertionError so existing rule-3 handling still catches it."""
