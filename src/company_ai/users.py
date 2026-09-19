"""Users & assignments — a small team over a shared CRM (docs/27).

Read surface: the roster, resolving the signed-in identity (email → user), the
assignment map (who owns which item), and "my work" (the entities assigned to a
user). Assignment lives in its own `assignments` collection, so reads join it
back onto contacts/todos/deals; the write path (log.set_assignment) never
touches the big tables. No prediction here — plumbing (rule 2).
"""

from dataclasses import dataclass, field

from .aito import AitoClient

ID_COL = {"contacts": "contact_id", "todos": "todo_id", "deals": "deal_id"}


@dataclass
class Result:
    calls: list = field(default_factory=list)
    derived: dict | None = None


def list_users(client: AitoClient, active_only: bool = True) -> list[dict]:
    """The roster, operator(s) first then by name. An unprovisioned instance
    (no `users` table yet) yields an empty roster rather than raising."""
    try:
        rows = client.query({"from": "users", "limit": 10000})["hits"]
    except Exception:
        return []
    if active_only:
        rows = [r for r in rows if r.get("active")]
    rows.sort(key=lambda u: (u.get("role") != "operator", u.get("name", "")))
    return rows


def resolve(client: AitoClient, email: str | None) -> dict | None:
    """The active user whose email matches the signed-in identity (case-folded).
    Returns None (guest) if the email is empty or the `users` table isn't
    provisioned yet — identity resolution must never 500 the app, and failing to
    a guest is the safe (least-privilege) direction."""
    if not email:
        return None
    email = email.strip().lower()
    try:
        hits = client.query({"from": "users", "where": {"email": email}, "limit": 1})["hits"]
    except Exception:
        return None
    for u in hits:
        return u if u.get("active") else None
    return None


def assignment_map(client: AitoClient, entity: str | None = None) -> dict:
    """{(entity, entity_id): user_id} — one owner per item (the write dedupes)."""
    request = {"from": "assignments", "limit": 100000}
    if entity:
        request["where"] = {"entity": entity}
    rows = client.query(request)["hits"]
    return {(r["entity"], r["entity_id"]): r["user_id"] for r in rows}


def _assigned_ids(client: AitoClient, user_id: str) -> dict:
    """{entity: {entity_id, ...}} assigned to this user."""
    rows = client.query({"from": "assignments", "where": {"user_id": user_id},
                         "limit": 100000})["hits"]
    out: dict = {e: set() for e in ID_COL}
    for r in rows:
        if r["entity"] in out:
            out[r["entity"]].add(r["entity_id"])
    return out


def my_work(client: AitoClient, user_id: str) -> Result:
    """The contacts, todos, and deals assigned to `user_id` — one focused lane
    across the shared CRM. Returns lightweight display rows per entity."""
    result = Result()
    ids = _assigned_ids(client, user_id)

    def pick(entity, id_col, fields):
        if not ids[entity]:
            return []
        rows = client.query({"from": entity, "limit": 100000})["hits"]
        return [{k: r.get(k) for k in ([id_col] + fields)}
                for r in rows if r[id_col] in ids[entity]]

    result.derived = {
        "user_id": user_id,
        "contacts": pick("contacts", "contact_id", ["name", "company", "segment", "tier"]),
        "todos": pick("todos", "todo_id", ["title", "area", "status", "priority", "due_date"]),
        "deals": pick("deals", "deal_id", ["company", "stage", "value_eur", "probability"]),
    }
    result.derived["count"] = sum(len(result.derived[e]) for e in ID_COL)
    return result
