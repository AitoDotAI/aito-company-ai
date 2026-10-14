"""The action surface: three lenses over the one todos table (rev 3 §2.9).

  - now      : cross-area, the most urgent open todos (the landing view)
  - pipeline : one area, ranked by priority (Operations, R&D)
  - calendar : one area, laid out by due_date (Sales, Distribution)

This is deterministic prioritisation — filter, sort, and a join to show the
linked company — not inference, so it lives in Python (CLAUDE.md rule 2
governs *predictive* logic; ordering a worklist by priority and due-date
proximity is formatting). The Aito layer over todos is a future addition:
once done/slipped history accrues, `_predict` slip-risk per todo is the
natural dogfood query, and it would *re-rank* the Now view. Until then the
ranking is honest and rule-based. See docs/12-todos-and-now.md.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date

from . import clock
from . import schema
from . import aitowhy, history
from .aito import AitoClient

# the open worklist excludes terminal todos: done (completed) and archived
# (abandoned). Both drop out of every lens; archived also advances nothing.
OPEN_STATUSES_EXCLUDED = schema.TERMINAL_STATUSES
# how far past/future a due date can be before it stops affecting urgency
_FAR = 9999


@dataclass
class Result:
    calls: list[tuple[str, dict, dict]] = field(default_factory=list)
    derived: dict | None = None


def _fetch(client: AitoClient, result: Result, table: str, where: dict | None = None,
           select: list[str] | None = None) -> list[dict]:
    request = {"from": table, "where": where or {}, "limit": 10000}
    if select:
        request["select"] = select
    response = client.query(request)
    result.calls.append(("_query", request, response))
    return response["hits"]


def _any_of(field: str, values) -> dict | None:
    values = sorted(v for v in values if v)
    if not values:
        return None
    return {field: values[0]} if len(values) == 1 else {"$or": [{field: v} for v in values]}


def _company_names(client: AitoClient, result: Result, todos: list[dict] | None = None) -> dict:
    """Lookup maps for the entities a todo references: `company` (id -> company,
    for both contacts and deals; their id namespaces don't collide) and
    `person` (contact_id -> name, for the stakeholder). Only the id/name/company
    columns are projected. Given `todos`, only the contacts and deals THEY
    reference are read (td-20261014123607349120); without, the whole tables."""
    if todos is None:
        c_where = d_where = {}
    else:
        ids = {t.get("stakeholder_id") for t in todos} | {
            t.get("linked_id") for t in todos if t.get("linked_type") in ("contact", "deal")}
        c_where, d_where = _any_of("contact_id", ids), _any_of("deal_id", ids)
    contacts = ([] if c_where is None else
                _fetch(client, result, "contacts", c_where, select=["contact_id", "company", "name"]))
    company = {c["contact_id"]: c["company"] for c in contacts}
    if d_where is not None:
        company.update({d["deal_id"]: d["company"] for d in
                        _fetch(client, result, "deals", d_where, select=["deal_id", "company"])})
    person = {c["contact_id"]: c["name"] for c in contacts}
    return {"company": company, "person": person}


# every todo column but the ticket body: what ranking needs. The body is the
# bulk of the table (about 3 MB of 3.8 on the live instance, 14.10), so a lens
# that shows a few rows ranks without it and fetches it for those rows only.
_LIST_COLUMNS = [c for c in schema.TODOS["columns"] if c != "detail"]
_OPEN = {"$and": [{"status": {"$not": s}} for s in sorted(schema.TERMINAL_STATUSES)]}


def _days_until(due: str | None, as_of: date) -> int | None:
    if not due:
        return None
    return (date.fromisoformat(due) - as_of).days


def _decorate(todo: dict, names: dict, as_of: date) -> dict:
    days = _days_until(todo.get("due_date"), as_of)
    co = names["company"]
    stakeholder_id = todo.get("stakeholder_id")
    # company derived (never stored): the stakeholder's company first, else the
    # linked deal/contact's
    company = co.get(stakeholder_id)
    if not company and todo.get("linked_type") in ("contact", "deal"):
        company = co.get(todo.get("linked_id"))
    return {
        "todo_id": todo["todo_id"],
        "area": todo["area"],
        "title": todo["title"],
        "detail": todo.get("detail"),
        "action_type": todo.get("action_type"),
        "status": todo["status"],
        "priority": todo["priority"],
        "due_date": todo.get("due_date"),
        "window": todo.get("window"),
        "slot": todo.get("slot"),
        "sort_order": todo.get("sort_order"),
        "prep_status": todo["prep_status"],
        "days_until_due": days,
        "overdue": days is not None and days < 0,
        # the linked record, surfaced so the action shows what it advances
        "linked_id": todo.get("linked_id"),
        "linked_type": todo.get("linked_type"),
        # the stakeholder (a contact) and the company, joined for display
        "stakeholder_id": stakeholder_id,
        "stakeholder": names["person"].get(stakeholder_id),
        "company": company,
        # work routing: which lane owns it, and which agent instance is holding
        # it (null = the lane's shared queue). Surfaced on every lens so the
        # operator can see who is on what without opening a row.
        "role": todo.get("role"),
        "owner": todo.get("owner"),
    }


def _slip_key(todo: dict) -> tuple:
    """The features the slip prediction conditions on. The prediction is a pure
    function of these, so two todos with the same key share one Aito call."""
    return (todo["area"], todo["priority"], todo["prep_status"])


def _slip_request(key: tuple) -> dict:
    area, priority, prep_status = key
    # learned from done todos only (history.finished): an open todo has not
    # slipped or kept its date yet, whatever its `slipped` column reads
    return {
        "from": history.finished("todos"),
        "where": {"area": area, "priority": priority, "prep_status": prep_status},
        "predict": "slipped",
        "select": ["$p", "$value", "$why"],
    }


def _slip_from_response(response: dict | None) -> dict | None:
    """Aito's P(this todo slips) + the feature driving it, from a predict
    response. None when there's no history to learn from (honest cold start)."""
    if response is None:
        return None
    hit = next((h for h in response.get("hits", []) if h["$value"] is True), None)
    if hit is None:
        return None
    factors = [
        {"label": _why_label(f["proposition"]), "lift": f["value"]}
        for f in aitowhy.lift_factors(hit)
    ]
    factors.sort(key=lambda w: -abs(w["lift"] - 1.0))
    return {"p": hit["$p"], "top_factor": factors[0]["label"] if factors else None}


def _annotate_slip_risk(client: AitoClient, result: Result, todos: list[dict]) -> None:
    """Attach Aito's slip-risk to each todo. The predictions are Aito's; this
    only changes how they're fetched — one call per *distinct* feature key
    (predictions are pure in the key), issued concurrently since they're
    independent. Serial per-todo round-trips to a remote instance were the Now
    view's whole latency (docs/12). `result.calls` is appended in sorted-key
    order so the fan-out stays deterministic for the booktest snapshot."""
    keys = sorted({_slip_key(t) for t in todos})
    if not keys:
        return

    def fetch(key: tuple):
        # None only for an empty history (no todo done yet); any other error raises
        return key, history.predict(client, _slip_request(key))

    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        fetched = dict(pool.map(fetch, keys))

    risk_by_key = {}
    for key in keys:  # deterministic order, not thread-completion order
        response = fetched[key]
        if response is not None:
            result.calls.append(("_predict", _slip_request(key), response))
        risk_by_key[key] = _slip_from_response(response)
    for todo in todos:
        todo["slip_risk"] = risk_by_key[_slip_key(todo)]


def _why_label(prop: dict) -> str:
    (key,) = prop.keys()
    if key == "$and":
        return " & ".join(_why_label(p) for p in prop[key])
    inner = prop[key]
    value = inner.get("$has") if isinstance(inner, dict) else inner
    return f"{key}={value}"


def _urgency_key(t: dict):
    """Lower sorts first. Overdue and due-soon high-priority work floats up;
    undated todos fall back to priority. A function of priority and due-date
    proximity, exactly as the spec frames Now."""
    days = t["days_until_due"]
    proximity = _FAR if days is None else max(days, -1)  # overdue clamps to most-urgent
    return (0 if t["overdue"] else 1, t["priority"], proximity, t["todo_id"])


def now(client: AitoClient, as_of: date | None = None, top_n: int = 8,
        with_slip_risk: bool = True) -> Result:
    """Cross-area: the most urgent open todos, for the landing view.

    Ordering is rule-based urgency; each surfaced todo is then annotated
    with Aito's slip-risk (a prediction, not part of the sort) so the
    operator sees both what's urgent and what's likely to slip."""
    as_of = as_of or clock.today()
    result = Result()
    # rank the open todos without their bodies, then read bodies and names
    # for the few that are shown (was: every todo, every field, plus the
    # whole contacts and deals tables, on every call)
    rows = [t for t in _fetch(client, result, "todos", _OPEN, select=_LIST_COLUMNS)
            if t["status"] not in OPEN_STATUSES_EXCLUDED]
    empty = {"company": {}, "person": {}}
    rows.sort(key=lambda t: _urgency_key(_decorate(t, empty, as_of)))
    rows = rows[:top_n]
    body_where = _any_of("todo_id", {t["todo_id"] for t in rows})
    bodies = ({} if body_where is None else
              {b["todo_id"]: b.get("detail") for b in
               _fetch(client, result, "todos", body_where, select=["todo_id", "detail"])})
    names = _company_names(client, result, rows)
    top = [_decorate({**t, "detail": bodies.get(t["todo_id"])}, names, as_of) for t in rows]
    if with_slip_risk:
        _annotate_slip_risk(client, result, top)
    result.derived = {"lens": "now", "as_of": as_of.isoformat(), "todos": top}
    return result


def pipeline(client: AitoClient, area: str, as_of: date | None = None) -> Result:
    """One area, in the operator's drag order when set, else by priority.
    sort_order (set by reorder) leads; priority stays the importance tag."""
    assert area in schema.TODO_AREAS, f"unknown area {area!r}"
    as_of = as_of or clock.today()
    result = Result()
    rows = [t for t in _fetch(client, result, "todos", {"$and": [{"area": area}, _OPEN]})
            if t["status"] not in OPEN_STATUSES_EXCLUDED]
    names = _company_names(client, result, rows)
    todos = [_decorate(t, names, as_of) for t in rows]
    # null sort_order sorts last → an un-dragged list is exactly priority order
    todos.sort(key=lambda t: (t["sort_order"] if t["sort_order"] is not None else 10**9,
                              t["priority"], t["todo_id"]))
    result.derived = {"lens": "pipeline", "area": area, "todos": todos}
    return result


def calendar(client: AitoClient, area: str, as_of: date | None = None) -> Result:
    """One area, laid out by due_date (the time-driven lens)."""
    assert area in schema.TODO_AREAS, f"unknown area {area!r}"
    as_of = as_of or clock.today()
    result = Result()
    rows = [t for t in _fetch(client, result, "todos", {"$and": [{"area": area}, _OPEN]})
            if t["status"] not in OPEN_STATUSES_EXCLUDED and t.get("due_date")]
    names = _company_names(client, result, rows)
    todos = [_decorate(t, names, as_of) for t in rows]
    todos.sort(key=lambda t: (t["due_date"], t["priority"], t["todo_id"]))
    result.derived = {"lens": "calendar", "area": area, "todos": todos}
    return result
