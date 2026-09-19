"""Action-surface gate: the three todo lenses on both datasets.

Snapshots the Now (cross-area urgency), pipeline (priority), and calendar
(date) lenses. as_of is pinned so urgency/overdue are deterministic. The
lenses are rule-based ordering, not inference, so this pins the ordering
contract the Now view and the action blocks depend on.
"""

from datetime import date

import booktest as bt

from company_ai import deals, loaders, log, schema, todos
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, SEED_TINY_DIR, Config

AS_OF = date(2026, 6, 14)


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _load(client: AitoClient, data_dir) -> None:
    loaders.create_schema(client)
    loaders.load_rolodex(client, data_dir)
    loaders.load_deals(client, data_dir)   # sales todos join to their deal's company
    loaders.load_todos(client, data_dir)


def _line(t: dict, slip: bool = False) -> str:
    co = f" [{t['company']}]" if t["company"] else ""
    due = t["due_date"] or "—"
    flag = " OVERDUE" if t["overdue"] else ""
    win = f" {t['window']}" if t["window"] else ""
    risk = ""
    if slip:
        sr = t.get("slip_risk")
        risk = f"  slip={sr['p']:.4f} ({sr['top_factor']})" if sr else "  slip=n/a"
    return f"  P{t['priority']} {t['area']:12} {due}{win}{flag}  {t['title']}{co}{risk}"


def test_now_lens_seed(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client, SEED_DIR)
    t.h1("Now lens with slip-risk (Aito prediction over closed-todo history)")
    for row in todos.now(client, as_of=AS_OF).derived["todos"]:
        t.tln(_line(row, slip=True))


def test_area_lenses_seed(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client, SEED_DIR)
    for area in ("sales", "marketing"):
        t.h1(f"Calendar lens: {area}")
        for row in todos.calendar(client, area, as_of=AS_OF).derived["todos"]:
            t.tln(_line(row))
    for area in ("operations", "rnd"):
        t.h1(f"Pipeline lens: {area}")
        for row in todos.pipeline(client, area, as_of=AS_OF).derived["todos"]:
            t.tln(_line(row))


def test_reorder_todos(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client, SEED_DIR)
    t.h1("Drag-reorder: sort_order leads, priority stays the importance tag")
    before = [x["todo_id"] for x in todos.pipeline(client, "rnd", as_of=AS_OF).derived["todos"]]
    t.tln(f"default order (by priority): {before}")
    log.reorder_todos(client, list(reversed(before)))
    after = todos.pipeline(client, "rnd", as_of=AS_OF).derived["todos"]
    t.tln(f"after reorder (reversed):    {[x['todo_id'] for x in after]}")
    t.tln(f"priorities unchanged (still the tag): {[x['priority'] for x in after]}")
    assert [x["todo_id"] for x in after] == list(reversed(before))

    t.h1("an unknown id raises (rule 3)")
    try:
        log.reorder_todos(client, ["nope"])
        raise RuntimeError("accepted unknown id")
    except AssertionError as e:
        t.tln(str(e))


def test_now_lens_seed_tiny(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client, SEED_TINY_DIR)
    t.h1("Now lens, tiny dataset")
    for row in todos.now(client, as_of=AS_OF).derived["todos"]:
        t.tln(_line(row))


def test_complete_todo_advances_linked_deal(t: bt.TestCaseRun) -> None:
    """The closed loop: completing a deal-linked sales todo marks it done
    (drops from the lenses) and advances its deal in the pipeline."""
    client = _client()
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_todos(client, SEED_DIR)

    # find an open sales todo that links to a deal
    sales = [x for x in todos.calendar(client, "sales", as_of=AS_OF).derived["todos"]
             if x["linked_type"] == "deal"]
    todo = sales[0]
    deal_id = todo["linked_id"]
    t.h1("Before")
    t.tln(f"todo {todo['todo_id']} links to deal {deal_id} ({todo['company']})")
    before_deal = next(d for d in deals.pipeline(client, as_of=AS_OF).derived["deals"]
                       if d["deal_id"] == deal_id)
    t.tln(f"deal stage={before_deal['stage']} probability={before_deal['probability']}")

    t.h1("Complete the todo, advancing the deal to negotiation @ 80%")
    result = log.complete_todo(client, todo["todo_id"], deal_stage="negotiation",
                               deal_probability=80, as_of=AS_OF)
    t.tln(f"todo status -> {result['todo']['status']}")
    t.tln(f"deal -> stage={result['deal']['stage']} probability={result['deal']['probability']}")

    t.h1("After: todo gone from the lens, deal advanced in the pipeline")
    open_ids = {x["todo_id"] for x in todos.calendar(client, "sales", as_of=AS_OF).derived["todos"]}
    assert todo["todo_id"] not in open_ids, "completed todo still in the calendar lens"
    after_deal = next(d for d in deals.pipeline(client, as_of=AS_OF).derived["deals"]
                      if d["deal_id"] == deal_id)
    assert after_deal["stage"] == "negotiation" and after_deal["probability"] == 80, \
        "deal did not advance"
    t.tln(f"confirmed: todo done & off the lens; deal now {after_deal['stage']} "
          f"@ {after_deal['probability']}% (weighted €{after_deal['weighted_value']:,})")


def test_archive_todo_abandons_without_advancing(t: bt.TestCaseRun) -> None:
    """Archiving abandons a todo: it becomes terminal (status=archived) and
    drops from the lenses, but — unlike complete — it advances no linked deal."""
    client = _client()
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_todos(client, SEED_DIR)

    sales = [x for x in todos.calendar(client, "sales", as_of=AS_OF).derived["todos"]
             if x["linked_type"] == "deal"]
    todo = sales[0]
    deal_id = todo["linked_id"]
    before_deal = next(d for d in deals.pipeline(client, as_of=AS_OF).derived["deals"]
                       if d["deal_id"] == deal_id)
    t.h1("Before")
    t.tln(f"todo {todo['todo_id']} ({todo['title']}) links deal {deal_id}")
    t.tln(f"deal stage={before_deal['stage']} probability={before_deal['probability']}")

    t.h1("Archive the todo")
    result = log.archive_todo(client, todo["todo_id"])
    t.tln(f"todo status -> {result['todo']['status']}")

    t.h1("After: todo gone from the lens; the linked deal is untouched")
    open_ids = {x["todo_id"] for x in todos.calendar(client, "sales", as_of=AS_OF).derived["todos"]}
    assert todo["todo_id"] not in open_ids, "archived todo still in the calendar lens"
    after_deal = next(d for d in deals.pipeline(client, as_of=AS_OF).derived["deals"]
                      if d["deal_id"] == deal_id)
    assert (after_deal["stage"], after_deal["probability"]) == \
        (before_deal["stage"], before_deal["probability"]), "archive must not advance the deal"
    t.tln(f"confirmed: todo archived & off the lens; deal still "
          f"{after_deal['stage']} @ {after_deal['probability']}%")


def test_handoff_block_required_to_enter_review(t: bt.TestCaseRun) -> None:
    """`review` means a human can check the work. That is only true if the claim
    is findable, so the HANDOFF block is a precondition rather than a convention.

    Filed after the 2026-08-31 read of the review queue: 83 items, 266,000
    characters, and 4 of 83 carried the block the agent brief calls mandatory."""
    full = ("did the work\n\n=== HANDOFF ===\n"
            "CLAIM:  the adapter now honours disjunctive filters\n"
            "VERIFY: ./do test book/test_x.py\n"
            "SCOPE:  did not touch the v1 path\n"
            "RISK:   untested against a migrated table\n"
            "PUSHED: fix/disjunctive-filters @ abc1234\n")

    def check(area, status, detail):
        problem = schema.handoff_problem(area, status, detail)
        return "accepted" if problem is None else "REJECTED: " + problem.split(".")[0]

    t.h1("R&D entering review needs the block")
    t.tln("  no block at all    -> " + check("rnd", "review", "did the work"))
    t.tln("  header only        -> " + check("rnd", "review", "=== HANDOFF ===\nCLAIM: x"))
    t.tln("  missing RISK       -> " + check("rnd", "review",
          full.replace("RISK:   untested against a migrated table\n", "")))
    t.tln("  complete block     -> " + check("rnd", "review", full))

    t.h1("Every other transition is untouched")
    t.tln("  rnd -> ready       -> " + check("rnd", "ready", "did the work"))
    t.tln("  rnd -> done        -> " + check("rnd", "done", "did the work"))
    t.tln("  rnd -> blocked     -> " + check("rnd", "blocked", "did the work"))

    t.h1("Only R&D — review elsewhere is not the agent-lane handoff")
    t.tln("  sales -> review    -> " + check("sales", "review", "did the work"))
    t.tln("  operations->review -> " + check("operations", "review", "did the work"))


def test_due_date_invariant_by_area(t: bt.TestCaseRun) -> None:
    # a complete, valid input row (derived sort_order excluded)
    base = {
        "todo_id": "x1", "area": "sales", "title": "call", "detail": "",
        "action_type": "", "status": "ready", "priority": "1", "due_date": "",
        "window": "", "slot": "", "linked_id": "", "linked_type": "",
        "stakeholder_id": "", "prep_status": "ready", "slipped": "",
        "role": "", "owner": "",   # work routing; unset on a plain operator todo
    }

    def parses(row):
        try:
            loaders.parse_todo_row(row)
            return "accepted"
        except AssertionError as e:
            return f"rejected: {str(e).split(';')[0]}"

    t.h1("Sales (calendar area) requires a due_date")
    t.tln("  no due_date  -> " + parses(base))
    t.tln("  with due_date -> " + parses({**base, "due_date": "2026-06-20"}))

    t.h1("Operations (deadline area) allows an OPTIONAL due_date")
    t.tln("  no due_date   -> " + parses({**base, "area": "operations"}))
    t.tln("  with due_date -> " + parses({**base, "area": "operations",
                                          "due_date": "2026-06-20", "slot": "10:00"}))

    t.h1("R&D (pipeline area) forbids a due_date")
    t.tln("  no due_date   -> " + parses({**base, "area": "rnd"}))
    t.tln("  with due_date -> " + parses({**base, "area": "rnd", "due_date": "2026-06-20"}))


def test_claim_todo_is_fail_if_taken(t: bt.TestCaseRun) -> None:
    """Eager claim (docs/12): an agent sets `owner` before working a lane's shared
    queue, so two agents don't pick the same item. A second agent claiming the
    same todo is refused (ClaimTaken); the owner re-claiming is idempotent. This
    pins the fail-if-taken contract the eager-claim loop and the claim_todo MCP
    tool depend on (best-effort — no hardware CAS; see docs/12)."""
    client = _client()
    loaders.create_schema(client)
    tid = log.add_todo(client, area="rnd", title="agent-lane work", priority=2,
                       action_type="research", role="core")["todo_id"]

    t.h1("claim_todo sets owner; a different agent is refused; the owner is idempotent")
    a = log.claim_todo(client, tid, "core-a")
    t.tln(f"core-a claim   -> owner={a['owner']} claimed={a['claimed']}")
    try:
        log.claim_todo(client, tid, "core-b")
        raise RuntimeError("core-b claim was accepted — must have raised")
    except log.ClaimTaken as e:
        t.tln(f"core-b claim   -> ClaimTaken, names the owner: {'core-a' in str(e)}")
    again = log.claim_todo(client, tid, "core-a")
    t.tln(f"core-a re-claim -> already_mine={again.get('already_mine')}")

    assert a["owner"] == "core-a" and a["claimed"]
    assert again.get("already_mine")
    log.archive_todo(client, tid)   # clean up for a repeatable run


def test_update_todo_owner_cannot_clobber_a_claim(t: bt.TestCaseRun) -> None:
    """update_todo must not be a side door around claim_todo (td-20260905163943977824).
    `owner` is editable, but writing it to a *different* live holder is a silent
    claim-steal, and the raise that claim_todo exists to make must fire here too.
    Allowed: a first claim on an unowned todo, an idempotent re-write of the same
    owner, and clearing (an operator freeing a dead claim). Refused: overwriting
    another agent's live claim — that goes through claim_todo, the guarded path."""
    client = _client()
    loaders.create_schema(client)
    tid = log.add_todo(client, area="rnd", title="guarded owner edit", priority=2,
                       action_type="research", role="core")["todo_id"]

    t.h1("unowned -> update_todo owner=core-a is a valid first claim")
    first = log.update_todo(client, tid, {"owner": "core-a"})
    t.tln(f"first claim via edit -> owner={first['owner']!r}")

    t.h1("owner=core-b over a live holder is refused — no silent steal")
    try:
        log.update_todo(client, tid, {"owner": "core-b"})
        raise RuntimeError("owner=core-b was accepted — must have raised")
    except log.ClaimTaken as e:
        t.tln(f"core-b edit -> ClaimTaken; names holder={'core-a' in str(e)} "
              f"points at claim_todo={'claim_todo' in str(e)}")

    t.h1("owner=core-a (the same holder) is idempotent")
    same = log.update_todo(client, tid, {"owner": "core-a"})
    t.tln(f"same-owner edit -> owner={same['owner']!r}")

    t.h1("owner='' clears the claim — an operator freeing a stuck agent")
    cleared = log.update_todo(client, tid, {"owner": ""})
    t.tln(f"clear edit -> owner={cleared['owner']!r}")

    assert first["owner"] == "core-a"
    assert same["owner"] == "core-a"
    assert cleared["owner"] is None
    log.archive_todo(client, tid)   # clean up for a repeatable run
