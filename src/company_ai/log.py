"""Outcome and decision logging: the only writes in the system.

Validation is the same loud kind the loaders use; a logged touch is
immediately queryable, which the round-trip booktest proves.
"""

import re
from datetime import date, datetime, timezone

from . import changelog, outbox, schema, search
from .aito import AitoClient
from .loaders import (parse_channel_row, parse_deal_row, parse_event_row,
                      parse_experiment_row, parse_material_row,
                      parse_post_row, parse_rolodex_row, parse_routine_row,
                      parse_session_row, parse_todo_row, parse_touch_row)
from .queries import bucket_days_since


def _stamp(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def add_contact(
    client: AitoClient,
    name: str,
    company: str,
    role: str,
    segment: str,
    tier: str,
    ai_lifecycle: str,
    source: str,
    country: str,
    phone_present: bool,
    email_present: bool,
    notes_tags: list[str] | None = None,
    created: str | None = None,
) -> dict:
    """Add a new person to the rolodex. Validated exactly like a CSV load
    (parse_rolodex_row), then appended to the live Aito instance — real
    contacts go to Aito, never to the repo's seed. A new contact has no
    touch history yet, so its funnel-stage flags start false."""
    raw = {
        "contact_id": _stamp("c"), "name": name, "company": company, "role": role,
        "segment": segment, "tier": tier, "ai_lifecycle": ai_lifecycle,
        "source": source, "country": country,
        "phone_present": "true" if phone_present else "false",
        "email_present": "true" if email_present else "false",
        "notes_tags": ";".join(notes_tags or []),
        "created": created or date.today().isoformat(),
    }
    row = parse_rolodex_row(raw)
    row.update({"ever_touched": False, "ever_reached": False,
                "ever_conversation": False, "ever_meeting": False})
    client.upload_batch("contacts", [row])
    search.refresh(client)
    return row


def add_company(client: AitoClient, name: str) -> dict:
    """Create (or confirm) a company entity — the link target that contacts,
    deals and documents point at via `company_id`. Idempotent on the name slug:
    adding a company that already exists returns the existing row untouched, so
    the note editor's 'new company' button is safe to press twice.

    A dangling `company_id` (a note or contact naming a company that has no
    entity row) is exactly what `load_companies` prevents at load time by
    scanning every source; this is the live-write equivalent for a company that
    first appears after the initial load."""
    from .loaders import company_slug
    assert name and name.strip(), "a company needs a name"
    name = name.strip()
    cid = company_slug(name)
    existing = client.query(
        {"from": "companies", "where": {"company_id": cid}, "limit": 1})["hits"]
    if existing:
        return {**existing[0], "created": False}
    row = {"company_id": cid, "name": name}
    client.upload_batch("companies", [row])
    return {**row, "created": True}


def add_deal(
    client: AitoClient,
    company: str,
    segment: str,
    stage: str,
    value_eur: int,
    probability: int,
    champion_present: bool,
    blocker: str = "none",
    created: str | None = None,
    as_of: date | None = None,
) -> dict:
    """Add a new opportunity to the pipeline. Validated like a CSV load
    (parse_deal_row, which derives `won` from the stage), then appended to
    the live Aito instance."""
    as_of = as_of or date.today()
    raw = {
        "deal_id": _stamp("d"), "company": company, "segment": segment, "stage": stage,
        "value_eur": str(value_eur), "probability": str(probability),
        "champion_present": "true" if champion_present else "false",
        "blocker": blocker, "last_touch_date": as_of.isoformat(),
        "created": created or as_of.isoformat(),
    }
    row = parse_deal_row(raw)
    client.upload_batch("deals", [row])
    changelog.record(client, "deal", row["deal_id"], "created",
                     f"deal created: {company} ({stage}, €{value_eur:,})")
    search.refresh(client)
    return row


def log_touch(
    client: AitoClient,
    contact_id: str,
    channel: str,
    window: str,
    outcome: str,
    next_action: str | None = None,
    next_action_due: str | None = None,
    notes: str | None = None,
    ts: datetime | None = None,
) -> dict:
    ts = ts or datetime.now().replace(microsecond=0)
    raw = {
        "touch_id": f"log-{ts.strftime('%Y%m%d%H%M%S')}-{contact_id}",
        "contact_id": contact_id,
        "ts": ts.isoformat(),
        "weekday": schema.WEEKDAYS[ts.weekday()],
        "window": window,
        "channel": channel,
        "outcome": outcome,
        "next_action": next_action or "",
        "next_action_due": next_action_due or "",
        "notes": notes or "",
    }
    contact_ids = {
        hit["contact_id"]
        for hit in client.query({"from": "contacts", "limit": 10000})["hits"]
    }
    row = parse_touch_row(raw, contact_ids)

    previous = client.query(
        {"from": "touches", "where": {"contact_id": contact_id}, "limit": 10000}
    )["hits"]
    days = None
    if previous:
        last = max(datetime.fromisoformat(t["ts"]).date() for t in previous)
        days = (ts.date() - last).days
    row["days_since_prev_touch"] = bucket_days_since(days)

    client.upload_batch("touches", [row])
    changelog.record(client, "touch", row["touch_id"], "logged",
                     f"{channel} to {contact_id}: {outcome}")
    return row


def log_decision(
    client: AitoClient,
    decision_type: str,
    context: dict,
    chosen: str,
    agent_confidence: float,
    human_action: str,
    human_alternative: str | None = None,
    outcome_after: str | None = None,
    ts: datetime | None = None,
) -> dict:
    ts = ts or datetime.now().replace(microsecond=0)
    assert decision_type in schema.DECISION_TYPES, f"unknown decision_type {decision_type!r}"
    assert human_action in schema.HUMAN_ACTIONS, f"unknown human_action {human_action!r}"
    context_keys = {"window", "weekday", "segment", "tier", "ai_lifecycle"}
    unknown = set(context) - context_keys
    assert not unknown, f"unknown context keys {sorted(unknown)}; allowed: {sorted(context_keys)}"
    assert 0.0 <= agent_confidence <= 1.0, f"agent_confidence out of [0,1]: {agent_confidence}"
    row = {
        "decision_id": f"dec-{ts.strftime('%Y%m%d%H%M%S')}-{decision_type}",
        "ts": ts.isoformat(),
        "decision_type": decision_type,
        **{f"context_{key}": context.get(key) for key in context_keys},
        "chosen": chosen,
        "agent_confidence": agent_confidence,
        "human_action": human_action,
        "human_alternative": human_alternative,
        "outcome_after": outcome_after,
        # derived (kept consistent with the loader for the dogfood scorecard)
        "confidence_bucket": schema.confidence_bucket(agent_confidence),
        "accepted": human_action == "accepted",
    }
    client.upload_batch("decisions", [row])
    return row


def log_deal_update(
    client: AitoClient,
    deal_id: str,
    stage: str | None = None,
    probability: int | None = None,
    blocker: str | None = None,
    champion_present: bool | None = None,
    as_of: date | None = None,
) -> dict:
    """Advance a deal: the closed loop from the action surface. Resolving a
    deal-linked todo (a call that booked a meeting, a stage that closed)
    updates the deal here, which immediately re-ranks the pipeline and
    re-derives `won` from the new stage. An Aito upsert by deal_id replaces
    the row, so this is idempotent."""
    as_of = as_of or date.today()
    # Aito exposes no per-row id to target, so update by rewriting the (small)
    # deals table: read all, swap the one row, reload. Idempotent, no
    # duplicate deal_ids. Nothing links to deals, so the drop is safe.
    all_deals = client.query({"from": "deals", "limit": 10000})["hits"]
    match = [d for d in all_deals if d["deal_id"] == deal_id]
    assert match, f"unknown deal_id {deal_id!r}"
    row = dict(match[0])
    if stage is not None:
        assert stage in schema.DEAL_STAGES, f"unknown stage {stage!r}"
        row["stage"] = stage
    if probability is not None:
        assert 0 <= probability <= 100, f"probability out of 0-100: {probability}"
        row["probability"] = probability
    if blocker is not None:
        assert blocker in schema.DEAL_BLOCKERS, f"unknown blocker {blocker!r}"
        row["blocker"] = blocker
    if champion_present is not None:
        row["champion_present"] = champion_present
    row["last_touch_date"] = as_of.isoformat()
    row["won"] = schema.deal_won(row["stage"])  # re-derive terminal state

    rewritten = [d for d in all_deals if d["deal_id"] != deal_id] + [row]
    client.delete_table("deals")
    client.create_table("deals", schema.DEALS)
    client.upload_batch("deals", rewritten)
    assert client.count("deals") == len(rewritten), "deal rewrite row-count mismatch"
    action = ("won" if row["stage"] == "closed_won"
              else "lost" if row["stage"] == "closed_lost" else "updated")
    changelog.record(client, "deal", deal_id, action,
                     f"deal {action}: {row['company']} → {row['stage']} ({row['probability']}%)",
                     detail={"stage": row["stage"], "probability": row["probability"],
                             "blocker": row.get("blocker")})
    search.refresh(client)
    return row


def complete_todo(
    client: AitoClient,
    todo_id: str,
    deal_stage: str | None = None,
    deal_probability: int | None = None,
    deal_blocker: str | None = None,
    champion_present: bool | None = None,
    as_of: date | None = None,
) -> dict:
    """Mark a todo done and, when it links to a deal, advance that deal —
    the closed loop. A sales todo carries linked_type=deal, so completing
    "call X" with the call's result (a stage move, a cleared blocker) flows
    straight into the pipeline via log_deal_update. Pass the deal_* changes
    the completion implies; omit them to just close the todo. Returns the
    updated todo and the updated deal (if any).

    Todos, like deals, are rewritten wholesale (Aito exposes no row id);
    the lenses already exclude status=done, so the completed todo drops out.
    """
    as_of = as_of or date.today()
    all_todos = client.query({"from": "todos", "limit": 10000})["hits"]
    match = [t for t in all_todos if t["todo_id"] == todo_id]
    assert match, f"unknown todo_id {todo_id!r}"
    todo = dict(match[0])
    todo["status"] = "done"
    rewritten = [t for t in all_todos if t["todo_id"] != todo_id] + [todo]
    client.delete_table("todos")
    client.create_table("todos", schema.TODOS)
    client.upload_batch("todos", rewritten)
    assert client.count("todos") == len(rewritten), "todo rewrite row-count mismatch"

    deal = None
    deal_change = any(v is not None for v in
                      (deal_stage, deal_probability, deal_blocker, champion_present))
    if todo.get("linked_type") == "deal" and todo.get("linked_id") and deal_change:
        deal = log_deal_update(
            client, todo["linked_id"], stage=deal_stage, probability=deal_probability,
            blocker=deal_blocker, champion_present=champion_present, as_of=as_of)
    changelog.record(client, "todo", todo_id, "done", f"done: {todo['title']}")
    return {"todo": todo, "deal": deal}


def archive_todo(client: AitoClient, todo_id: str) -> dict:
    """Archive (abandon) a todo — a terminal state distinct from done. Unlike
    complete_todo it advances nothing (no deal move, no outcome logged); it
    just drops the action from the open lenses, which already exclude terminal
    statuses. One full-table rewrite (Aito exposes no row id). Unknown id
    raises (rule 3). Returns the updated todo."""
    all_todos = client.query({"from": "todos", "limit": 10000})["hits"]
    match = [t for t in all_todos if t["todo_id"] == todo_id]
    assert match, f"unknown todo_id {todo_id!r}"
    todo = dict(match[0])
    todo["status"] = "archived"
    rewritten = [t for t in all_todos if t["todo_id"] != todo_id] + [todo]
    client.delete_table("todos")
    client.create_table("todos", schema.TODOS)
    client.upload_batch("todos", rewritten)
    assert client.count("todos") == len(rewritten), "todo rewrite row-count mismatch"
    changelog.record(client, "todo", todo_id, "archived", f"archived: {todo['title']}")
    return {"todo": todo}


def reorder_todos(client: AitoClient, ordered_ids: list[str]) -> int:
    """Persist a drag-reorder: set sort_order = position for each id in
    `ordered_ids` (the visible list, top → bottom). One full-table rewrite, so
    a drag costs a single write, not N. Unknown ids raise (rule 3)."""
    all_todos = client.query({"from": "todos", "limit": 10000})["hits"]
    by_id = {t["todo_id"]: t for t in all_todos}
    unknown = [i for i in ordered_ids if i not in by_id]
    assert not unknown, f"unknown todo_id(s) {unknown}"
    for position, tid in enumerate(ordered_ids):
        by_id[tid]["sort_order"] = position
    client.delete_table("todos")
    client.create_table("todos", schema.TODOS)
    client.upload_batch("todos", list(by_id.values()))
    assert client.count("todos") == len(by_id), "todo rewrite row-count mismatch"
    return len(ordered_ids)


def _todo_link_ids(client: AitoClient) -> tuple[set[str], set[str]]:
    contact_ids = {c["contact_id"] for c in client.query({"from": "contacts", "limit": 100000})["hits"]}
    deal_ids = {d["deal_id"] for d in client.query({"from": "deals", "limit": 100000})["hits"]}
    return contact_ids, deal_ids


def add_todo(
    client: AitoClient,
    area: str,
    title: str,
    priority: int,
    status: str = "ready",
    prep_status: str = "ready",
    action_type: str | None = None,
    due_date: str | None = None,
    window: str | None = None,
    slot: str | None = None,
    linked_id: str | None = None,
    linked_type: str | None = None,
    stakeholder_id: str | None = None,
    detail: str | None = None,
    role: str | None = None,
    owner: str | None = None,
) -> dict:
    """Add an action to the todos table (validated like a CSV load, written
    to the live Aito instance). Calendar areas (sales, marketing) need a
    due_date; pipeline areas (operations, rnd, experiments) must not. `slot`
    is an HH:MM clock time shown in the calendar. A todo can link a deal
    (linked_type=deal) and a stakeholder (a contact), validated live.

    `role` routes the work to a lane (a repo slug, a surface, `operator`) — an
    agent filters its queue on it. `owner` names one agent instance within that
    lane, for when a role is run by more than one agent; leaving it null means
    the role's shared queue."""
    raw = {
        "todo_id": _stamp("td"), "area": area, "title": title, "detail": detail or "",
        "action_type": action_type or "", "status": status, "priority": str(priority),
        "due_date": due_date or "", "window": window or "", "slot": slot or "",
        "linked_id": linked_id or "", "linked_type": linked_type or "",
        "stakeholder_id": stakeholder_id or "", "prep_status": prep_status, "slipped": "",
        "role": role or "", "owner": owner or "",
    }
    problem = schema.handoff_problem(area, status, detail)
    assert not problem, f"todo {title!r}: {problem}"

    contact_ids, deal_ids = _todo_link_ids(client)
    row = parse_todo_row(raw, contact_ids, deal_ids)
    client.upload_batch("todos", [row])
    changelog.record(client, "todo", row["todo_id"], "created", f"todo: {title} ({area})")
    return row


# the fields an operator may edit on an existing todo (todo_id is the key;
# slipped is outcome-only, set at completion)
EDITABLE_TODO_FIELDS = {"area", "title", "action_type", "status", "priority",
                        "due_date", "window", "slot", "linked_id", "linked_type",
                        "stakeholder_id", "prep_status", "detail", "role", "owner"}


def update_todo(client: AitoClient, todo_id: str, changes: dict,
                as_of: date | None = None) -> dict:
    """Edit a todo (the dashboard's edit form). Validates each changed field
    against its enum/format, re-checks the calendar/pipeline due-date
    invariant, and rewrites the table (Aito exposes no row id). Unknown fields
    or values raise — no silent coercion (rule 3)."""
    unknown = set(changes) - EDITABLE_TODO_FIELDS
    assert not unknown, f"not editable: {sorted(unknown)}; allowed {sorted(EDITABLE_TODO_FIELDS)}"
    all_todos = client.query({"from": "todos", "limit": 10000})["hits"]
    match = [t for t in all_todos if t["todo_id"] == todo_id]
    assert match, f"unknown todo_id {todo_id!r}"
    row = dict(match[0])
    current_owner = row.get("owner") or ""   # read before the loop overwrites it

    contact_ids, deal_ids = _todo_link_ids(client)
    for field, value in changes.items():
        if field == "area":
            assert value in schema.TODO_AREAS, f"unknown area {value!r}"
        elif field == "status":
            assert value in schema.TODO_STATUS, f"unknown status {value!r}"
        elif field == "prep_status":
            assert value in schema.PREP_STATUS, f"unknown prep_status {value!r}"
        elif field == "action_type" and value:
            assert value in schema.ACTION_TYPES, f"unknown action_type {value!r}"
        elif field == "linked_type" and value:
            assert value in schema.LINKED_TYPES, f"unknown linked_type {value!r}"
        elif field == "priority":
            value = int(value)
            assert value >= 1, f"priority must be >= 1, got {value}"
        elif field == "stakeholder_id" and value:
            assert value in contact_ids, f"unknown stakeholder_id {value!r}"
        elif field == "role" and value:
            assert re.fullmatch(schema.SLUG_PATTERN, value), \
                f"role must be a lowercase slug, got {value!r}"
        elif field == "owner" and value:
            assert re.fullmatch(schema.SLUG_PATTERN, value), \
                f"owner must be a lowercase slug, got {value!r}"
            # owner is editable, but claiming is claim_todo's job: overwriting a
            # *different* live holder here would silently steal the claim the
            # ClaimTaken guard exists to protect (td-20260905163943977824).
            # Allowed: first claim (unowned), idempotent re-write (same owner),
            # and clearing (value "" -> None below, an operator freeing a claim).
            if current_owner and value != current_owner:
                raise ClaimTaken(
                    f"{todo_id} is owned by {current_owner!r}; use claim_todo "
                    f"(the guarded path) or clear the owner first")
        row[field] = value if value != "" else None

    problem = schema.handoff_problem(row["area"], row["status"], row.get("detail"))
    assert not problem, f"todo {todo_id}: {problem}"

    if row.get("linked_type") == "deal" and row.get("linked_id"):
        assert row["linked_id"] in deal_ids, f"unknown deal linked_id {row['linked_id']!r}"
    # the lens invariant on the open worklist (mirrors parse_todo_row); terminal
    # todos (done/archived) are exempt — they're off the worklist
    if row["status"] not in schema.TERMINAL_STATUSES:
        if row["area"] in schema.CALENDAR_AREAS:
            assert row.get("due_date"), f"open {row['area']} todo needs a due_date"
        elif row["area"] not in schema.DEADLINE_AREAS:
            assert not row.get("due_date"), f"open {row['area']} todo must not have a due_date"

    rewritten = [t for t in all_todos if t["todo_id"] != todo_id] + [row]
    client.delete_table("todos")
    client.create_table("todos", schema.TODOS)
    client.upload_batch("todos", rewritten)
    assert client.count("todos") == len(rewritten), "todo rewrite row-count mismatch"
    changelog.record(client, "todo", todo_id, "updated",
                     f"updated: {row['title']} ({', '.join(sorted(changes))})", detail=changes)
    return row


class ClaimTaken(RuntimeError):
    """A todo an agent tried to claim is already owned by a different agent."""


def _todo(client: AitoClient, todo_id: str) -> dict:
    hits = client.query({"from": "todos", "where": {"todo_id": todo_id}, "limit": 1})["hits"]
    assert hits, f"unknown todo_id {todo_id!r}"
    return hits[0]


def claim_todo(client: AitoClient, todo_id: str, agent: str) -> dict:
    """Eagerly claim a todo for `agent` (its `owner`). **Fails (`ClaimTaken`) if
    another agent already owns it.** Idempotent if you already own it. Sets only
    `owner` — it does not start, complete, or move the work.

    Best-effort, NOT a hardware compare-and-set (Aito exposes none — docs/12,
    wishlist #7): a read-check rejects a todo already owned by someone else (no
    stealing — the common case), then a single-field `update_entries` sets `owner`
    (it flushes, read-your-writes), and a read-BACK reports the holder. This
    narrows the race to the ~millisecond window between one claimant's read-check
    and its write commit: two agents that BOTH read the same *free* todo as
    unclaimed in that window can still both proceed (each can read back its own id
    before the other overwrites). That is rare — agents pull different top items —
    and the `review` gate + a human close catch a double-worked ticket. A hard
    guarantee needs engine-level atomic CAS / rows-affected (wishlist)."""
    assert agent and re.fullmatch(schema.SLUG_PATTERN, agent), \
        f"agent must be a lowercase slug (an owner id), got {agent!r}"
    current = (_todo(client, todo_id).get("owner") or "")
    if current and current != agent:
        raise ClaimTaken(f"{todo_id} is already owned by {current!r}")
    if current == agent:
        return {"todo_id": todo_id, "owner": agent, "claimed": True, "already_mine": True}
    client.update_entries("todos", {"todo_id": todo_id}, {"owner": agent})  # flushes
    holder = (_todo(client, todo_id).get("owner") or "")
    if holder != agent:                       # lost a simultaneous race
        raise ClaimTaken(f"{todo_id} was claimed by {holder!r} first")
    changelog.record(client, "todo", todo_id, "claimed", f"claimed by {agent}")
    return {"todo_id": todo_id, "owner": agent, "claimed": True}


def add_material(client: AitoClient, type: str, title: str, topic: str,
                 lane: str, ai_made: str, length_chars: int,
                 created: str | None = None) -> dict:
    """Add a content artifact (blog post, demo, …) to the materials catalog."""
    raw = {"material_id": _stamp("mat"), "type": type, "title": title,
           "topic": topic, "lane": lane, "ai_made": ai_made,
           "length_chars": str(length_chars), "created": created or date.today().isoformat()}
    row = parse_material_row(raw)
    client.upload_batch("materials", [row])
    return row


def add_channel(client: AitoClient, name: str, platform: str,
                created: str | None = None) -> dict:
    """Add a destination (Hacker News, r/programming, LinkedIn) to the channels
    catalog. A channel rolls up to a platform."""
    raw = {"channel_id": _stamp("ch"), "name": name, "platform": platform,
           "created": created or date.today().isoformat()}
    row = parse_channel_row(raw)
    client.upload_batch("channels", [row])
    return row


def _material_channel_maps(client: AitoClient) -> tuple[dict, dict]:
    materials = {m["material_id"]: m for m in client.query({"from": "materials", "limit": 100000})["hits"]}
    channels = {c["channel_id"]: c for c in client.query({"from": "channels", "limit": 100000})["hits"]}
    return materials, channels


def add_post(client: AitoClient, material_id: str, channel_id: str, tone: str,
             format: str, link_placement: str, status: str = "planned") -> dict:
    """Plan a post: a material posted to a channel, with a go/no-go status
    (default planned). KPIs arrive once posted, via log_post_result. The
    material's/channel's attributes are denormalized in (validated live)."""
    raw = {
        "post_id": _stamp("po"), "material_id": material_id, "channel_id": channel_id,
        "status": status, "posted_at": "", "tone": tone, "format": format,
        "link_placement": link_placement, "reach_or_views": "", "upvotes": "",
        "trials": "", "outcome": "",
    }
    materials, channels = _material_channel_maps(client)
    row = parse_post_row(raw, materials, channels)
    client.upload_batch("posts", [row])
    return row


def log_post_result(client: AitoClient, post_id: str, outcome: str,
                    reach_or_views: int, upvotes: int = 0, trials: int = 0,
                    posted_at: str | None = None) -> dict:
    """Mark a planned post posted and record its KPIs — the measure step.
    Re-derives `won`/`weekday`. Full-table rewrite (Aito exposes no row id)."""
    assert outcome in schema.POST_OUTCOMES, f"unknown outcome {outcome!r}"
    all_posts = client.query({"from": "posts", "limit": 100000})["hits"]
    match = [p for p in all_posts if p["post_id"] == post_id]
    assert match, f"unknown post_id {post_id!r}"
    row = dict(match[0])
    when = posted_at or date.today().isoformat()
    row.update({
        "status": "posted", "posted_at": when,
        "weekday": schema.WEEKDAYS[date.fromisoformat(when[:10]).weekday()],
        "outcome": outcome, "reach_or_views": int(reach_or_views),
        "upvotes": int(upvotes), "trials": int(trials),
        "won": schema.post_won("posted", outcome),
    })
    rewritten = [p for p in all_posts if p["post_id"] != post_id] + [row]
    client.delete_table("posts")
    client.create_table("posts", schema.POSTS)
    client.upload_batch("posts", rewritten)
    assert client.count("posts") == len(rewritten), "post rewrite row-count mismatch"
    changelog.record(client, "post", post_id, "posted", f"post {outcome}: {reach_or_views} reach")
    return row


def log_session(
    client: AitoClient,
    source: str,
    landing_page: str,
    country: str,
    device: str,
    signed_up: bool,
    started_trial: bool,
    converted_paid: bool,
    campaign: str | None = None,
    ts: str | None = None,
) -> dict:
    """Log a website session to the acquisition funnel (validated like a CSV
    load, incl. the monotonicity invariant: paid => trial => signup)."""
    raw = {
        "session_id": _stamp("ss"), "ts": ts or date.today().isoformat(),
        "source": source, "campaign": campaign or "", "landing_page": landing_page,
        "country": country, "device": device,
        "signed_up": "true" if signed_up else "false",
        "started_trial": "true" if started_trial else "false",
        "converted_paid": "true" if converted_paid else "false",
    }
    row = parse_session_row(raw)
    client.upload_batch("sessions", [row])
    return row


def add_experiment(
    client: AitoClient,
    area: str,
    type: str,
    hypothesis: str,
    metric: str,
    baseline: float,
    target: float,
    effort: str,
    created: str | None = None,
) -> dict:
    """Start a Build-Measure-Learn experiment (the Build step). Validated like
    a CSV load (parse_experiment_row); a new experiment is `running` with no
    result yet. area is an AARRR stage, target is the metric value that would
    validate the bet."""
    when = created or date.today().isoformat()
    raw = {
        "experiment_id": _stamp("ex"), "created": when, "area": area, "type": type,
        "hypothesis": hypothesis, "metric": metric, "baseline": str(baseline),
        "target": str(target), "result": "", "effort": effort, "status": "running",
        "learning": "", "started": when, "decided": "",
    }
    row = parse_experiment_row(raw)
    client.upload_batch("experiments", [row])
    return row


def log_experiment_result(
    client: AitoClient,
    experiment_id: str,
    status: str,
    result: float,
    learning: str | None = None,
    as_of: date | None = None,
) -> dict:
    """Resolve a running experiment to a verdict (the Learn step): record the
    measured result, the validated learning, and a terminal status
    (validated/invalidated/inconclusive), which re-derives `validated` and so
    re-ranks the learning board. As with deals, Aito exposes no per-row id, so
    this rewrites the (small) experiments table; idempotent."""
    as_of = as_of or date.today()
    assert status in schema.EXPERIMENT_TERMINAL, \
        f"a result needs a terminal verdict (validated/invalidated/inconclusive), got {status!r}"
    all_ex = client.query({"from": "experiments", "limit": 10000})["hits"]
    match = [e for e in all_ex if e["experiment_id"] == experiment_id]
    assert match, f"unknown experiment_id {experiment_id!r}"
    row = dict(match[0])
    row["status"] = status
    row["result"] = float(result)
    if learning is not None:
        row["learning"] = learning
    row["decided"] = as_of.isoformat()
    row["validated"] = schema.experiment_validated(status)

    rewritten = [e for e in all_ex if e["experiment_id"] != experiment_id] + [row]
    client.delete_table("experiments")
    client.create_table("experiments", schema.EXPERIMENTS)
    client.upload_batch("experiments", rewritten)
    assert client.count("experiments") == len(rewritten), "experiment rewrite row-count mismatch"
    changelog.record(client, "experiment", experiment_id, status,
                     f"experiment {status}: {row['hypothesis'][:60]}")
    return row


def add_event(client: AitoClient, name: str, type: str, starts: str,
              location: str | None = None, cost_eur: int | None = None,
              notes: str | None = None) -> dict:
    """Record an event to attend, as a `candidate` (the go/no-go decision comes
    later via decide_event). Validated like a CSV load."""
    raw = {
        "event_id": _stamp("ev"), "name": name, "type": type, "starts": starts,
        "location": location or "", "cost_eur": "" if cost_eur is None else str(cost_eur),
        "status": "candidate", "decided": "", "outcome": "", "notes": notes or "",
        "created": date.today().isoformat(),
    }
    row = parse_event_row(raw)
    client.upload_batch("events", [row])
    return row


def decide_event(client: AitoClient, event_id: str, status: str,
                 outcome: str | None = None, notes: str | None = None,
                 as_of: date | None = None) -> dict:
    """Make (or revise) the go/no-go on an event: status go / no_go / attended.
    `attended` may carry an outcome (worthwhile/neutral/waste). Full-table
    rewrite (Aito exposes no row id). The decision date is stamped."""
    as_of = as_of or date.today()
    assert status in schema.EVENT_STATUS, f"unknown status {status!r}"
    all_events = client.query({"from": "events", "limit": 100000})["hits"]
    match = [e for e in all_events if e["event_id"] == event_id]
    assert match, f"unknown event_id {event_id!r}"
    row = dict(match[0])
    row["status"] = status
    row["decided"] = as_of.isoformat() if status != "candidate" else None
    if outcome is not None:
        assert outcome in schema.EVENT_OUTCOMES, f"unknown outcome {outcome!r}"
        assert status == "attended", "an outcome is only graded on an attended event"
        row["outcome"] = outcome
    if status != "attended":
        row["outcome"] = None  # clear any stale grade if un-attending
    if notes is not None:
        row["notes"] = notes
    rewritten = [e for e in all_events if e["event_id"] != event_id] + [row]
    client.delete_table("events")
    client.create_table("events", schema.EVENTS)
    client.upload_batch("events", rewritten)
    assert client.count("events") == len(rewritten), "event rewrite row-count mismatch"
    changelog.record(client, "event", event_id, status, f"event {status}: {row['name']}")
    return row


def add_routine(client: AitoClient, title: str, area: str, cadence: str,
                prep: str = "none", weekday: str | None = None,
                day_of_month: int | None = None, prompt: str | None = None,
                notes: str | None = None) -> dict:
    """Add a recurring routine (validated like a CSV load). cadence:
    daily/weekly/monthly — weekly needs a weekday, monthly a day_of_month."""
    raw = {
        "routine_id": _stamp("rt"), "title": title, "area": area, "cadence": cadence,
        "weekday": weekday or "", "day_of_month": "" if day_of_month is None else str(day_of_month),
        "prep": prep, "prompt": prompt or "", "last_done": "", "active": "true",
        "notes": notes or "", "created": date.today().isoformat(),
    }
    row = parse_routine_row(raw)
    client.upload_batch("routines", [row])
    changelog.record(client, "routine", row["routine_id"], "created", f"routine: {title} ({cadence})")
    return row


# fields an operator may edit on a routine
EDITABLE_ROUTINE_FIELDS = {"title", "area", "cadence", "weekday", "day_of_month",
                           "prep", "prompt", "active", "notes"}


def _rewrite_routine(client: AitoClient, routine_id: str, mutate) -> dict:
    all_routines = client.query({"from": "routines", "limit": 10000})["hits"]
    match = [r for r in all_routines if r["routine_id"] == routine_id]
    assert match, f"unknown routine_id {routine_id!r}"
    row = dict(match[0])
    mutate(row)
    rewritten = [r for r in all_routines if r["routine_id"] != routine_id] + [row]
    client.delete_table("routines")
    client.create_table("routines", schema.ROUTINES)
    client.upload_batch("routines", rewritten)
    assert client.count("routines") == len(rewritten), "routine rewrite row-count mismatch"
    return row


def update_routine(client: AitoClient, routine_id: str, changes: dict) -> dict:
    """Edit a routine (the customizable list). Validates enums; rewrites the
    table. Unknown fields/values raise (rule 3)."""
    unknown = set(changes) - EDITABLE_ROUTINE_FIELDS
    assert not unknown, f"not editable: {sorted(unknown)}; allowed {sorted(EDITABLE_ROUTINE_FIELDS)}"
    if "area" in changes:
        assert changes["area"] in schema.TODO_AREAS, f"unknown area {changes['area']!r}"
    if "cadence" in changes:
        assert changes["cadence"] in schema.ROUTINE_CADENCE, f"unknown cadence {changes['cadence']!r}"
    if "prep" in changes:
        assert changes["prep"] in schema.ROUTINE_PREP, f"unknown prep {changes['prep']!r}"
    if changes.get("weekday"):
        assert changes["weekday"] in schema.WEEKDAYS, f"unknown weekday {changes['weekday']!r}"
    if changes.get("day_of_month") not in (None, ""):
        changes["day_of_month"] = int(changes["day_of_month"])

    def mutate(row):
        for k, v in changes.items():
            row[k] = v if v != "" else None
    row = _rewrite_routine(client, routine_id, mutate)
    changelog.record(client, "routine", routine_id, "updated",
                     f"updated routine: {row['title']}", detail=changes)
    return row


def tick_routine(client: AitoClient, routine_id: str, as_of: date | None = None) -> dict:
    """Mark a routine done for the current period (stamps last_done). The
    board re-computes due-ness from it."""
    when = (as_of or date.today()).isoformat()
    row = _rewrite_routine(client, routine_id, lambda row: row.update({"last_done": when}))
    changelog.record(client, "routine", routine_id, "done", f"routine done: {row['title']}")
    return row


# ── advisors (the advisory board roster; config, runtime-editable) ─────────
EDITABLE_ADVISOR_FIELDS = {"name", "persona", "mandate", "reads", "rank", "active"}


def _valid_reads(reads: list[str]) -> None:
    from . import board
    bad = [r for r in reads if r not in board.READS]
    assert not bad, f"unknown read(s) {bad}; have {sorted(board.READS)}"


def _reads_list(reads) -> list[str]:
    if isinstance(reads, str):
        reads = [s.strip() for s in reads.split(",")]
    return [r for r in reads if r]


def _ensure_advisors_seeded(client: AitoClient) -> None:
    """Advisors is config seeded from board.toml. On an instance that predates
    the table (or was never seeded), materialise the default roster before the
    first edit — so an edit never silently drops the other advisors."""
    from . import board
    try:
        rows = client.query({"from": "advisors", "limit": 1000})["hits"]
    except Exception:
        rows = None                      # table doesn't exist yet
    if rows:
        return
    if rows is None:
        client.create_table("advisors", schema.ADVISORS)
    seed = [board.advisor_to_row(a, i * 10) for i, a in enumerate(board.default_roster())]
    if seed:
        client.upload_batch("advisors", seed)


def add_advisor(client: AitoClient, advisor_id: str, name: str, mandate: str,
                reads: list[str], persona: str | None = None,
                rank: int | None = None) -> dict:
    """Add an advisor to the board (config write). `reads` must be board.READS
    names. A duplicate id or an unknown read raises (rule 3)."""
    _ensure_advisors_seeded(client)
    reads = _reads_list(reads)
    _valid_reads(reads)
    existing = client.query({"from": "advisors", "limit": 10000})["hits"]
    assert advisor_id not in {r["advisor_id"] for r in existing}, \
        f"advisor_id {advisor_id!r} already exists"
    if rank is None:
        rank = max((r.get("rank", 0) for r in existing), default=0) + 10
    row = {"advisor_id": advisor_id, "name": name, "persona": persona or None,
           "mandate": mandate, "reads": ",".join(reads), "rank": int(rank),
           "active": True, "created": date.today().isoformat()}
    client.upload_batch("advisors", [row])
    changelog.record(client, "advisor", advisor_id, "created", f"advisor: {name}")
    return row


def _rewrite_advisor(client: AitoClient, advisor_id: str, mutate) -> dict:
    all_adv = client.query({"from": "advisors", "limit": 10000})["hits"]
    match = [r for r in all_adv if r["advisor_id"] == advisor_id]
    assert match, f"unknown advisor_id {advisor_id!r}"
    row = dict(match[0])
    mutate(row)
    rewritten = [r for r in all_adv if r["advisor_id"] != advisor_id] + [row]
    client.delete_table("advisors")
    client.create_table("advisors", schema.ADVISORS)
    client.upload_batch("advisors", rewritten)
    assert client.count("advisors") == len(rewritten), "advisor rewrite row-count mismatch"
    return row


def update_advisor(client: AitoClient, advisor_id: str, changes: dict) -> dict:
    """Edit an advisor (persona, mandate, reads, order, active). Validates each
    field; rewrites the table. Unknown fields/values raise (rule 3)."""
    _ensure_advisors_seeded(client)
    unknown = set(changes) - EDITABLE_ADVISOR_FIELDS
    assert not unknown, f"not editable: {sorted(unknown)}; allowed {sorted(EDITABLE_ADVISOR_FIELDS)}"
    changes = dict(changes)
    if "reads" in changes:
        reads = _reads_list(changes["reads"])
        _valid_reads(reads)
        changes["reads"] = ",".join(reads)
    if "rank" in changes:
        changes["rank"] = int(changes["rank"])
    if "active" in changes:
        changes["active"] = bool(changes["active"])

    def mutate(row):
        for k, v in changes.items():
            row[k] = (v or None) if k == "persona" else v
    row = _rewrite_advisor(client, advisor_id, mutate)
    changelog.record(client, "advisor", advisor_id, "updated",
                     f"updated advisor: {row['name']} ({', '.join(sorted(changes))})", detail=changes)
    return row


def remove_advisor(client: AitoClient, advisor_id: str) -> dict:
    """Remove an advisor from the board. Unknown id raises (rule 3)."""
    _ensure_advisors_seeded(client)
    all_adv = client.query({"from": "advisors", "limit": 10000})["hits"]
    assert advisor_id in {r["advisor_id"] for r in all_adv}, f"unknown advisor_id {advisor_id!r}"
    rewritten = [r for r in all_adv if r["advisor_id"] != advisor_id]
    client.delete_table("advisors")
    client.create_table("advisors", schema.ADVISORS)
    if rewritten:
        client.upload_batch("advisors", rewritten)
    assert client.count("advisors") == len(rewritten), "advisor rewrite row-count mismatch"
    changelog.record(client, "advisor", advisor_id, "removed", f"removed advisor: {advisor_id}")
    return {"removed": advisor_id, "remaining": len(rewritten)}


def _check_contact(client: AitoClient, stakeholder_id: str | None) -> None:
    if not stakeholder_id:
        return
    ids = {c["contact_id"] for c in client.query({"from": "contacts", "limit": 100000})["hits"]}
    assert stakeholder_id in ids, f"unknown stakeholder_id {stakeholder_id!r}"


# ---- documents (the knowledge store, docs/25) ----

def _check_document(client: AitoClient, kind: str, area: str | None,
                    stakeholder_id: str | None) -> None:
    assert kind in schema.DOC_KINDS, f"unknown kind {kind!r}; have {sorted(schema.DOC_KINDS)}"
    assert area in (None, "") or area in schema.DOCUMENT_AREAS, \
        f"unknown area {area!r}; have {sorted(schema.DOCUMENT_AREAS)}"
    _check_contact(client, stakeholder_id)


def add_document(client: AitoClient, title: str, body: str, kind: str = "internal",
                 area: str | None = None, company: str | None = None,
                 stakeholder_id: str | None = None, source: str | None = None,
                 topics: str | None = None, noted_on: str | None = None) -> dict:
    """Create a document in the knowledge store. Validated like a load: an
    unknown kind/area or a dangling contact link raises (rule 3). `kind` is
    docs|internal; `area` optional; `company`/`stakeholder_id` optional links;
    `topics` a ';'-joined free-form list; `noted_on` the diary day (ISO), which
    turns the note into a dated diary entry (docs/25 Phase 2)."""
    from .loaders import company_slug
    _check_document(client, kind, area, stakeholder_id)
    assert title and body, "a document needs a title and a body"
    if noted_on:
        date.fromisoformat(noted_on)   # loud on a malformed diary date (rule 3)
    now = date.today().isoformat()
    company = company or None
    row = {
        "doc_id": _stamp("dc"), "title": title, "body": body, "kind": kind,
        "area": area or None, "topics": topics or None, "noted_on": noted_on or None,
        "company": company, "company_id": company_slug(company) if company else None,
        "stakeholder_id": stakeholder_id or None, "source": source or None,
        "created": now, "updated": now,
    }
    client.upload_batch("documents", [row])
    changelog.record(client, "documents", row["doc_id"], "created", f"document: {title}")
    search.refresh(client)
    return row


EDITABLE_DOCUMENT_FIELDS = {"title", "body", "kind", "area", "company", "stakeholder_id",
                            "topics", "noted_on"}


def _rewrite_documents(client: AitoClient, doc_id: str, mutate) -> list[dict]:
    rows = client.query({"from": "documents", "limit": 100000})["hits"]
    match = [r for r in rows if r["doc_id"] == doc_id]
    assert match, f"unknown doc_id {doc_id!r}"
    kept = mutate([dict(r) for r in rows])
    client.delete_table("documents")
    client.create_table("documents", schema.DOCUMENTS)
    if kept:
        client.upload_batch("documents", kept)
    assert client.count("documents") == len(kept), "documents rewrite row-count mismatch"
    return kept


def update_document(client: AitoClient, doc_id: str, changes: dict) -> dict:
    """Edit a document. Validates kind/area/contact; rewrites the table (the
    full-rewrite pattern, never `_modify`). Stamps `updated`."""
    unknown = set(changes) - EDITABLE_DOCUMENT_FIELDS
    assert not unknown, f"not editable: {sorted(unknown)}; allowed {sorted(EDITABLE_DOCUMENT_FIELDS)}"
    if "kind" in changes:
        assert changes["kind"] in schema.DOC_KINDS, f"unknown kind {changes['kind']!r}"
    if changes.get("area"):
        assert changes["area"] in schema.DOCUMENT_AREAS, f"unknown area {changes['area']!r}"
    if changes.get("stakeholder_id"):
        _check_contact(client, changes["stakeholder_id"])
    if changes.get("noted_on"):
        date.fromisoformat(changes["noted_on"])   # loud on a malformed diary date (rule 3)
    from .loaders import company_slug
    edited = {}

    def mutate(rows):
        for row in rows:
            if row["doc_id"] == doc_id:
                for k, v in changes.items():
                    row[k] = v if v != "" else None
                if "company" in changes:   # keep the entity link in step with the string
                    row["company_id"] = company_slug(row["company"]) if row["company"] else None
                row["updated"] = date.today().isoformat()
                edited.update(row)
        return rows
    _rewrite_documents(client, doc_id, mutate)
    search.refresh(client)
    return edited


def delete_document(client: AitoClient, doc_id: str) -> dict:
    """Remove a document."""
    _rewrite_documents(client, doc_id, lambda rows: [r for r in rows if r["doc_id"] != doc_id])
    search.refresh(client)
    return {"deleted": doc_id}


def import_documents(client: AitoClient, rows: list[dict]) -> dict:
    """Bulk-load scanned documents (documents.scan_dir) into the store, one
    stamped row each. Idempotent on `source`: a file already imported (same
    relative path) is replaced, not duplicated. Returns a small report."""
    from .loaders import company_slug
    existing = client.query({"from": "documents", "limit": 100000})["hits"]
    by_source = {r.get("source"): r for r in existing if r.get("source")}
    now = date.today().isoformat()
    added, replaced = 0, 0
    kept = [dict(r) for r in existing]
    for scanned in rows:
        _check_document(client, scanned["kind"], scanned.get("area"),
                        scanned.get("stakeholder_id"))
        prior = by_source.get(scanned.get("source"))
        if prior:
            kept = [r for r in kept if r["doc_id"] != prior["doc_id"]]
            doc_id, created = prior["doc_id"], prior.get("created", now)
            replaced += 1
        else:
            doc_id, created = _stamp("dc"), now
            added += 1
        company = scanned.get("company") or None
        kept.append({"doc_id": doc_id, "title": scanned["title"], "body": scanned["body"],
                     "kind": scanned["kind"], "area": scanned.get("area") or None,
                     "topics": scanned.get("topics") or None,
                     "noted_on": scanned.get("noted_on") or None,
                     "company": company,
                     "company_id": company_slug(company) if company else None,
                     "stakeholder_id": scanned.get("stakeholder_id") or None,
                     "source": scanned.get("source") or None,
                     "created": created, "updated": now})
    client.delete_table("documents")
    client.create_table("documents", schema.DOCUMENTS)
    if kept:
        client.upload_batch("documents", kept)
    search.refresh(client)
    return {"added": added, "replaced": replaced, "total": len(kept)}


def _journal_topics(kind: str | None, tags: str | None,
                    linked_type: str | None, linked_id: str | None) -> str | None:
    """Fold a journal row's structure that documents lack into the free-form
    topics: the entry `kind` (except the generic 'note'), its ';'-joined `tags`,
    and a deal link as `deal:<id>` (.ai/tasks/15 Phase 2d). Order-preserving,
    de-duplicated."""
    parts: list[str] = []
    if kind and kind != "note":
        parts.append(kind)
    parts += [t.strip() for t in (tags or "").split(";") if t.strip()]
    if linked_type == "deal" and linked_id:
        parts.append(f"deal:{linked_id}")
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return ";".join(out) or None


def migrate_journal(client: AitoClient) -> dict:
    """One-shot: fold every `journal` entry into `documents` as a dated note
    (`.ai/tasks/15` Phase 2d — the journal is being retired into the documents
    diary). The entry's `date` becomes `noted_on`; its `kind`/`tags`/deal-link
    fold into `topics`; company/stakeholder links carry over (company_id derived).
    Idempotent on `source='journal:<entry_id>'` — re-running replaces, never
    duplicates — so it is safe to run before the journal table is dropped. Run on
    prod once (a `migrate-journal` CLI wraps this). Returns a report."""
    from .loaders import company_slug
    entries = client.query({"from": "journal", "limit": 1_000_000})["hits"]
    existing = client.query({"from": "documents", "limit": 1_000_000})["hits"]
    by_source = {r.get("source"): r for r in existing if r.get("source")}
    company_ids = _company_id_names(client)   # to recover a lost link from the tags
    now = date.today().isoformat()
    kept = [dict(r) for r in existing]
    added = replaced = 0
    for j in entries:
        source = f"journal:{j['entry_id']}"
        prior = by_source.get(source)
        if prior:
            kept = [r for r in kept if r["doc_id"] != prior["doc_id"]]
            doc_id, created = prior["doc_id"], prior.get("created", now)
            replaced += 1
        else:
            doc_id, created = _stamp("dc"), j.get("created") or now
            added += 1
        topics = _journal_topics(j.get("kind"), j.get("tags"),
                                  j.get("linked_type"), j.get("linked_id"))
        company = j.get("company") or None
        company_id = company_slug(company) if company else None
        if not company:   # the entry lost its link; recover it from the tags
            company, company_id = _company_from_topics(topics, company_ids)
        kept.append({
            "doc_id": doc_id, "title": j["title"], "body": j["body"], "kind": "internal",
            "area": None,
            "topics": topics,
            "noted_on": j.get("date") or None,
            "company": company, "company_id": company_id,
            "stakeholder_id": j.get("stakeholder_id") or None,
            "source": source, "created": created, "updated": now,
        })
    client.delete_table("documents")
    client.create_table("documents", schema.DOCUMENTS)
    if kept:
        client.upload_batch("documents", kept)
    search.refresh(client)
    return {"migrated": added, "replaced": replaced, "documents_total": len(kept)}


def _company_id_names(client: AitoClient) -> dict[str, str]:
    """{company_id slug -> name} for CANONICAL company entities — the lookup table
    for recovering a document's company from its topic tags. Rows whose `name`
    equals their own slug (e.g. 'overview', 'unknown') are auto-created junk, not
    real accounts; excluding them stops a generic topic token from false-matching
    one (a real company's display name always differs from its lowercase slug)."""
    return {x["company_id"]: x["name"]
            for x in client.query({"from": "companies", "limit": 1_000_000})["hits"]
            if x["name"] != x["company_id"]}


def _company_from_topics(topics: str | None,
                         company_ids: dict[str, str]) -> tuple[str | None, str | None]:
    """Literal lookup (rule 2, not prediction): a topic token that IS a known
    `company_id` slug names the document's company. Journal-derived documents
    lost their `company`/`company_id` at harvest time but kept the slug in
    `topics` (td-20260909105919886359). Returns (name, company_id) when EXACTLY
    one topic token is a company_id; (None, None) otherwise — zero or several
    matches are reported by the caller, never guessed (rule 3)."""
    hits = sorted({tk for tk in (topics or "").split(";") if tk and tk in company_ids})
    return (company_ids[hits[0]], hits[0]) if len(hits) == 1 else (None, None)


def backfill_document_companies(client: AitoClient, *, apply: bool = False) -> dict:
    """Recover the company link on journal-derived documents that lost it at
    harvest time (td-20260909105919886359), so the knowledge store is browsable
    by account again (documents_list(company=X) / the diary rollup). The company
    slug survives in `topics`; when exactly one topic token is a known company_id
    we set `company` (and the derived `company_id`). Literal lookup only — no
    prediction (rule 2). Documents whose topics name zero or several companies
    are left null and counted, never guessed (rule 3).

    `apply=False` (default) is a DRY RUN: it changes nothing and returns the
    planned edits for review. `apply=True` rewrites the documents table ONCE
    (the full-rewrite pattern, not one update_document per row) and refreshes the
    search view. Idempotent: an already-linked document is skipped."""
    company_ids = _company_id_names(client)
    rows = client.query({"from": "documents", "limit": 1_000_000})["hits"]
    kept, planned, ambiguous = [], [], 0
    for d in rows:
        row = dict(d)
        if not row.get("company"):
            toks = [tk for tk in (row.get("topics") or "").split(";") if tk]
            hits = sorted({tk for tk in toks if tk in company_ids})
            if len(hits) == 1:
                row["company"], row["company_id"] = company_ids[hits[0]], hits[0]
                planned.append({"doc_id": row["doc_id"], "company": row["company"],
                                "title": d.get("title")})
            elif len(hits) > 1:
                ambiguous += 1
        kept.append(row)
    null_before = sum(1 for d in rows if not d.get("company"))
    if apply and planned:
        client.delete_table("documents")
        client.create_table("documents", schema.DOCUMENTS)
        client.upload_batch("documents", kept)
        assert client.count("documents") == len(kept), "documents rewrite row-count mismatch"
        search.refresh(client)
    return {"applied": apply, "resolved": len(planned), "ambiguous": ambiguous,
            "left_null": null_before - len(planned), "planned": planned}


# ---- users & assignments (the small team, docs/27) ----

_ASSIGN_ID_COL = {"contacts": "contact_id", "todos": "todo_id", "deals": "deal_id"}


def add_user(client: AitoClient, name: str, email: str, role: str = "sdr",
             active: bool = True) -> dict:
    """Add a user (operator adds the SDR). Role in USER_ROLES; email unique and
    case-folded (it is matched against the Entra Easy Auth identity)."""
    assert role in schema.USER_ROLES, f"unknown role {role!r}; have {sorted(schema.USER_ROLES)}"
    assert name and email, "a user needs a name and an email"
    email = email.strip().lower()
    if client.query({"from": "users", "where": {"email": email}, "limit": 1})["hits"]:
        raise AssertionError(f"a user with email {email!r} already exists")
    row = {"user_id": _stamp("u"), "name": name, "email": email, "role": role,
           "active": bool(active), "created": date.today().isoformat()}
    client.upload_batch("users", [row])
    changelog.record(client, "users", row["user_id"], "created", f"user: {name} ({role})")
    return row


def update_user(client: AitoClient, user_id: str, changes: dict) -> dict:
    """Edit a user (name / email / role / active). Full-rewrite (small table)."""
    fields = {"name", "email", "role", "active"}
    unknown = set(changes) - fields
    assert not unknown, f"not editable: {sorted(unknown)}; allowed {sorted(fields)}"
    if "role" in changes:
        assert changes["role"] in schema.USER_ROLES, f"unknown role {changes['role']!r}"
    rows = client.query({"from": "users", "limit": 10000})["hits"]
    assert any(u["user_id"] == user_id for u in rows), f"unknown user_id {user_id!r}"
    edited = {}
    kept = []
    for u in rows:
        u = dict(u)
        if u["user_id"] == user_id:
            for k, v in changes.items():
                u[k] = v.strip().lower() if k == "email" else v
            edited = u
        kept.append(u)
    client.delete_table("users")
    client.create_table("users", schema.USERS)
    client.upload_batch("users", kept)
    changelog.record(client, "users", user_id, "updated", f"user {user_id}")
    return edited


def set_assignment(client: AitoClient, entity: str, entity_id: str,
                   user_id: str | None) -> dict:
    """Assign (or, with user_id falsy, unassign) a work item to a user. Writes
    the `assignments` join table by full-rewrite — one owner per item, and the
    big/linked CRM tables are never touched (docs/27). Validates the entity, the
    item, and the user (rule 3)."""
    assert entity in schema.ASSIGNABLE_ENTITIES, \
        f"not assignable: {entity!r}; have {sorted(schema.ASSIGNABLE_ENTITIES)}"
    user_id = user_id or None
    if user_id:
        us = client.query({"from": "users", "where": {"user_id": user_id}, "limit": 1})["hits"]
        assert us and us[0].get("active"), f"unknown or inactive user {user_id!r}"
    id_col = _ASSIGN_ID_COL[entity]
    if not client.query({"from": entity, "where": {id_col: entity_id}, "limit": 1})["hits"]:
        raise AssertionError(f"unknown {entity} {entity_id!r}")
    rows = client.query({"from": "assignments", "limit": 100000})["hits"]
    kept = [dict(r) for r in rows
            if not (r["entity"] == entity and r["entity_id"] == entity_id)]
    if user_id:
        kept.append({"assignment_id": _stamp("as"), "entity": entity, "entity_id": entity_id,
                     "user_id": user_id, "created": date.today().isoformat()})
    client.delete_table("assignments")
    client.create_table("assignments", schema.ASSIGNMENTS)
    if kept:
        client.upload_batch("assignments", kept)
    changelog.record(client, "assignments", entity_id, "updated",
                     f"{entity} {entity_id} -> {user_id or 'unassigned'}")
    return {"entity": entity, "entity_id": entity_id, "user_id": user_id}


# ---- API tokens (remote MCP, docs/28) ----

def add_token(client: AitoClient, label: str) -> dict:
    """Mint a named bearer token for the remote MCP. Generates a strong secret,
    stores ONLY its SHA-256 hash (+ a short prefix + label), and returns the
    plaintext ONCE — it is never stored and cannot be recovered."""
    import secrets as _secrets
    from . import tokens as tokens_mod
    assert label and label.strip(), "a token needs a label"
    secret = _secrets.token_urlsafe(40)
    row = {"token_id": _stamp("tok"), "label": label.strip(),
           "token_hash": tokens_mod.hash_token(secret), "prefix": secret[:8],
           "created": date.today().isoformat(), "active": True}
    client.upload_batch("tokens", [row])
    changelog.record(client, "tokens", row["token_id"], "created", f"token: {label}")
    return {"token_id": row["token_id"], "label": row["label"],
            "prefix": row["prefix"], "token": secret}   # plaintext, shown once


def revoke_token(client: AitoClient, token_id: str) -> dict:
    """Revoke a token (active=false) — effective on the next request. Full-rewrite
    of the small tokens table (never `_modify`)."""
    rows = client.query({"from": "tokens", "limit": 100000})["hits"]
    assert any(r["token_id"] == token_id for r in rows), f"unknown token_id {token_id!r}"
    kept = []
    for r in rows:
        r = dict(r)
        if r["token_id"] == token_id:
            r["active"] = False
        kept.append(r)
    client.delete_table("tokens")
    client.create_table("tokens", schema.TOKENS)
    if kept:
        client.upload_batch("tokens", kept)
    changelog.record(client, "tokens", token_id, "updated", "token revoked")
    return {"revoked": token_id}


# ---- outbox (staged outbound, authorised by a human — docs/30) ----

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _outbox_write(client: AitoClient, outbox_id: str, changes: dict) -> dict:
    """Apply `changes` to one outbox row and return the row as it now reads.

    `update_entries` does the `_modify` update and flushes (optimize) so the
    change is visible to reads — on this build a bare update stays invisible until
    the next write, and an approval the operator cannot see is worse than no
    approval at all. The row is then read back and the change asserted — a
    silently stale write raises rather than returning a lie (rule 3). No
    full-table rewrite here: the outbox holds real recipients and real bodies, and
    drop-and-reload would put every one of them through a delete/restore window
    for a one-field edit."""
    client.update_entries("outbox", {"outbox_id": outbox_id}, changes)
    row = outbox.read(client, outbox_id)
    stale = {k: v for k, v in changes.items() if row.get(k) != v}
    assert not stale, (
        f"outbox {outbox_id} did not take the update {sorted(stale)} — reads still show "
        f"{ {k: row.get(k) for k in stale} }. Refusing to report a write that did not land."
    )
    return row


def stage_outbox(client: AitoClient, to: str, contact_name: str, company: str,
                 subject: str, body: str, send_after: str, outbox_class: str,
                 rationale: str, agent: str, cc: str | None = None,
                 thread_id: str | None = None, reply_to_message_id: str | None = None,
                 no_thread: bool = False, channel: str = "email") -> dict:
    """Stage one outbound message for the operator to authorise (status=staged).

    This writes a row; it sends nothing. `outbox_class` is the spec's `class`
    column (first_touch / re_entry / logistics / campaign / referral_ask).
    `rationale` is the one line the approval view shows — why this, why now.
    `send_after` is the intended window (ISO date or datetime).

    Threading is a precondition, not a nicety: pass `thread_id` +
    `reply_to_message_id` when a thread with this contact exists, or
    `no_thread=True` to state explicitly that you resolved the threads and there
    is none (outbox.check_thread). `body` is the final plain text — nothing is
    templated at send time, so an unresolved placeholder raises here."""
    assert channel in schema.OUTBOX_CHANNELS, \
        f"unknown channel {channel!r}; have {sorted(schema.OUTBOX_CHANNELS)}"
    assert outbox_class in schema.OUTBOX_CLASSES, \
        f"unknown class {outbox_class!r}; have {sorted(schema.OUTBOX_CLASSES)}"
    for name, value in {"to": to, "contact_name": contact_name, "company": company,
                        "subject": subject, "body": body, "rationale": rationale,
                        "agent": agent}.items():
        assert value and str(value).strip(), f"an outbox row needs a {name}"
    assert "@" in to, f"to {to!r} is not an address"
    assert "{{" not in body and "{{" not in subject, (
        "body/subject still carry an unresolved {{placeholder}} — the staged text is "
        "what goes out verbatim; there is no send-time templating"
    )
    outbox.check_thread(thread_id, reply_to_message_id, no_thread)
    now = _now()
    row = {
        "outbox_id": _stamp("ob"), "created": now, "updated": now,
        "channel": channel, "to": to, "cc": cc or None,
        "contact_name": contact_name, "company": company,
        "subject": subject, "body": body,
        "thread_id": thread_id or None, "reply_to_message_id": reply_to_message_id or None,
        "send_after": outbox.parse_ts(send_after, "send_after"),
        "class": outbox_class, "status": "staged", "agent": agent,
        "rationale": rationale, "message_id": None, "sent_at": None, "result": None,
    }
    outbox._ensure(client)
    client.upload_batch("outbox", [row])
    outbox.remember_staged(row["outbox_id"])
    changelog.record(client, "outbox", row["outbox_id"], "staged",
                     f"outbox staged ({outbox_class}) → {company}: {subject}",
                     detail={"agent": agent, "send_after": send_after,
                             "threaded": bool(thread_id)})
    return row


# what the operator may fix before approving. Not `status` (that is the decision
# path), not the send-result columns (those are written after a send).
EDITABLE_OUTBOX_FIELDS = {"to", "cc", "subject", "body", "send_after", "rationale",
                          "thread_id", "reply_to_message_id", "class"}


def update_outbox(client: AitoClient, outbox_id: str, changes: dict) -> dict:
    """Edit a staged message before approving it (the approval view's Edit).
    Only a `staged` row is editable — once approved, the text the operator
    signed off is the text that goes out. Validated like a stage (rule 3)."""
    unknown = set(changes) - EDITABLE_OUTBOX_FIELDS
    assert not unknown, \
        f"not editable: {sorted(unknown)}; allowed {sorted(EDITABLE_OUTBOX_FIELDS)}"
    row = outbox.read(client, outbox_id)
    assert row["status"] == "staged", \
        f"outbox {outbox_id} is {row['status']}, not staged — only a staged message is editable"
    clean = {}
    for field, value in changes.items():
        value = value if value not in ("",) else None
        if field == "class":
            assert value in schema.OUTBOX_CLASSES, f"unknown class {value!r}"
        elif field == "send_after":
            value = outbox.parse_ts(value, "send_after")
        elif field in ("to", "subject", "body", "rationale"):
            assert value and str(value).strip(), f"{field} cannot be emptied"
            if field == "to":
                assert "@" in value, f"to {value!r} is not an address"
        clean[field] = value
    merged = {**row, **clean}
    # On an edit only the pairing half of the thread rule applies: a thread_id
    # must still carry the message it replies to, and a reply id without a
    # thread is still refused. The "I searched and there is no thread" claim was
    # made at stage time; it is not re-asked of an operator fixing a typo.
    outbox.check_thread(merged["thread_id"], merged["reply_to_message_id"],
                        no_thread=True)
    clean["updated"] = _now()
    edited = _outbox_write(client, outbox_id, clean)
    changelog.record(client, "outbox", outbox_id, "updated",
                     f"outbox edited: {edited['subject']} → {edited['company']}",
                     detail={"fields": sorted(changes)})
    return edited


def approve_outbox(client: AitoClient, outbox_id: str, decision: str,
                   approved_by: str, source: str = "ui") -> dict:
    """The human decision on a staged message: `approved` or `struck`.

    `approved_by` names who decided (the ai.i route passes the signed-in
    identity) and is recorded in the change log — the outbox columns are fixed by
    the spec, so the audit of *who* lives there. `source` is the surface the
    decision came through: `ui` is the operator in ai.i, anything else is an
    agent, and an agent may not approve a row its own session staged
    (outbox.forbid_self_approval).

    Only `staged` moves. An already-approved or struck row is not re-decided
    here — a second opinion on a sent message is not a state transition."""
    assert decision in schema.OUTBOX_DECISIONS, \
        f"unknown decision {decision!r}; have {sorted(schema.OUTBOX_DECISIONS)}"
    assert approved_by and approved_by.strip(), \
        "approve_outbox needs approved_by — every decision names its decider"
    outbox.forbid_self_approval(outbox_id, decision, source)
    row = outbox.read(client, outbox_id)
    assert row["status"] == "staged", (
        f"outbox {outbox_id} is {row['status']}, not staged — only a staged message "
        "can be approved or struck"
    )
    decided = _outbox_write(client, outbox_id, {"status": decision, "updated": _now()})
    changelog.record(client, "outbox", outbox_id, decision,
                     f"outbox {decision} by {approved_by}: {decided['subject']} "
                     f"→ {decided['company']}",
                     detail={"by": approved_by, "source": source,
                             "class": decided["class"]})
    return decided
