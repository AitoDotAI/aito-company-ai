"""The change log: an append-only audit of what changed (docs/22).

Every meaningful mutation — a todo created/done/archived, a deal won/lost —
appends one row to Aito's `changelog` table (a single cheap
insert, no rewrite). The write functions in log.py call `record()`; `recent()`
reads it back, newest first, for the dashboard's Activity view, the MCP tool,
and the assistant. Later these roll up into daily/weekly notes (see the task
note).

Timestamps are real (UTC); tests pass a fixed `at` for deterministic snapshots.
"""

import json
import uuid
from datetime import datetime, timezone

from . import schema
from .aito import AitoClient


def record(client: AitoClient, entity: str, entity_id: str, action: str,
           summary: str, detail: dict | None = None, at: str | None = None) -> dict:
    """Append one change-log entry. `entity` (todo/deal/…), `action`
    (created/updated/done/won/lost/…), `summary` a one-line human description."""
    client.ensure_table("changelog", schema.CHANGELOG)
    row = {
        "change_id": "chg_" + uuid.uuid4().hex[:12],
        "at": at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entity": entity, "entity_id": entity_id, "action": action,
        "summary": summary,
        "detail": json.dumps(detail, default=str) if detail is not None else None,
    }
    client.upload_batch("changelog", [row])
    return row


# The most rows one `recent()` call returns. Aito aborts any response over
# 10 MB (nginx then answers 502); a changelog row is ~2.2 kB, so the cap sits
# far below the ~4,466-row failure point and no caller can reintroduce it.
MAX_RECENT = 1000


def recent(client: AitoClient, limit: int = 50, entity: str | None = None,
           since: str | None = None) -> dict:
    """The most recent changes, newest first (optionally filtered to one entity
    kind). `since` (an ISO datetime lower bound, inclusive) windows to activity
    on or after that instant — e.g. the board's last-week focus. Returns
    {changes, count} where count is the number of changes in the window.

    Ordering, filtering and the limit are all server-side: the changelog is
    append-only and grows without bound, so fetching it whole and sorting in
    Python eventually exceeds the response cap (the 502 of 2026-11-03).
    `limit` is clamped to MAX_RECENT."""
    assert isinstance(limit, int) and limit >= 0, f"limit must be a non-negative int: {limit!r}"
    client.ensure_table("changelog", schema.CHANGELOG)
    where: dict = {"entity": entity} if entity else {}
    if since:
        where["at"] = {"$gte": since}
    response = client.query({"from": "changelog", "where": where,
                             "orderBy": {"$desc": "at"},
                             "limit": min(limit, MAX_RECENT)})
    changes = [{"at": r["at"], "entity": r["entity"], "entity_id": r["entity_id"],
                "action": r["action"], "summary": r["summary"]} for r in response["hits"]]
    return {"changes": changes, "count": response["total"]}
