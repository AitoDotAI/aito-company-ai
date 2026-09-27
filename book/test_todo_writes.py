"""Todo writes are row-addressed and version-checked, never a table rewrite.

The board incident of 2026-09-26 (td-20260926165345475422): update / complete
/ archive rewrote the whole todos table (read all -> DROP -> CREATE ->
re-upload). Two overlapping calls doubled the table, a timed-out one lost
rows, readers saw an empty or missing table, and a success response echoed
the intended row rather than the persisted one.

The first tests drive the real `log` functions against an in-memory engine
that forces the interleavings (two writers reading the same version, a write
that dies half-way, a stale read). The last one runs the concurrent cases
against a real Aito, inside a throwaway env (opt-in, like test_envkit).
"""

import copy
import os
import re
import threading
from datetime import date

import booktest as bt
from company_ai import loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _todo(todo_id: str, **over) -> dict:
    row = {"todo_id": todo_id, "area": "operations", "title": f"task {todo_id}",
           "detail": None, "action_type": None, "status": "ready", "priority": 2,
           "due_date": None, "window": None, "slot": None, "sort_order": None,
           "linked_id": None, "linked_type": None, "stakeholder_id": None,
           "prep_status": "ready", "slipped": None, "role": "lane", "owner": None,
           "rev": None}
    row.update(over)
    return row


class FakeAito:
    """The engine surface the todo writes use, with `_modify` semantics: an
    update touches exactly the rows whose fields EQUAL the where; a null in the
    where matches nothing (measured on aito-core 2.10).
    Hooks let a test pause a writer or make reads stale; `table_absent_reads`
    counts reads that found the todos table empty, which must stay 0."""

    base_url = "fake://board"

    def __init__(self, rows):
        self.tables = {"todos": copy.deepcopy(rows), "changelog": [], "contacts": [], "deals": []}
        self.lock = threading.Lock()
        self.before_update = None        # hook(where, set) -> None
        self.drop_updates = False        # the engine accepts a write but applies nothing
        self.stale_reads = 0             # the next N todo reads return the pre-write row
        self._stale = None
        self.table_absent_reads = 0

    def get_schema(self):
        return {"schema": {"todos": {"columns": {k: {} for k in self.tables["todos"][0]}}}}

    def ensure_table(self, name, definition):
        self.tables.setdefault(name, [])

    def add_column(self, table, column, definition):
        for r in self.tables[table]:
            r.setdefault(column, None)

    def query(self, body):
        with self.lock:
            rows = self.tables.get(body["from"], [])
            if body["from"] == "todos" and not rows:
                self.table_absent_reads += 1
            where = body.get("where", {})
            hits = [r for r in rows if all(r.get(k) == v for k, v in where.items())]
            if body["from"] == "todos" and self.stale_reads and self._stale is not None:
                self.stale_reads -= 1
                hits = [s for s in self._stale if all(s.get(k) == v for k, v in where.items())]
            return {"hits": copy.deepcopy(hits[: body.get("limit", 10000)]), "total": len(hits)}

    def count(self, table):
        return len(self.tables[table])

    def update_entries(self, table, where, set_fields):
        if self.before_update:
            self.before_update(where, set_fields)
        with self.lock:
            self._stale = copy.deepcopy(self.tables[table])
            if self.drop_updates:
                return {}
            for r in self.tables[table]:
                # as measured on aito-core 2.10: a `where` naming a null value
                # matches nothing (it is not "field is unset")
                if all(v is not None and r.get(k) == v for k, v in where.items()):
                    r.update(set_fields)
            return {}

    def upload_batch(self, table, rows):
        with self.lock:
            self.tables.setdefault(table, []).extend(copy.deepcopy(rows))

    def delete_table(self, name):               # must never be called on the write path
        raise AssertionError(f"delete_table({name!r}) on the write path")

    def create_table(self, name, definition):
        raise AssertionError(f"create_table({name!r}) on the write path")


def _board(n=3):
    return FakeAito([_todo(f"td-{i}") for i in range(1, n + 1)])


def _row(fake, todo_id):
    return next(r for r in fake.tables["todos"] if r["todo_id"] == todo_id)


def _pause_first_writer_until_second_has_read(fake):
    """Force the race: writer A reads, then waits at its write until writer B
    has read the same version and written. A's write then matches nothing."""
    a_waiting, b_written = threading.Event(), threading.Event()
    first = {"taken": False}

    def hook(where, set_fields):
        with fake.lock:
            me_first = not first["taken"]
            first["taken"] = True
        if me_first:
            a_waiting.set()
            b_written.wait(5)
        else:
            a_waiting.wait(5)
    orig = fake.update_entries

    def update(table, where, set_fields):
        orig(table, where, set_fields)
        if first["taken"] and a_waiting.is_set():
            b_written.set()
    fake.before_update = hook
    fake.update_entries = update


def _run(*fns):
    errors = []

    def wrap(fn):
        try:
            fn()
        except Exception as e:   # noqa: BLE001 - surfaced in the snapshot
            errors.append(f"{type(e).__name__}: {e}")
    threads = [threading.Thread(target=wrap, args=(f,)) for f in fns]
    for th in threads:
        th.start()
    for th in threads:
        th.join(10)
    return errors


def test_concurrent_writes_on_different_rows_and_an_add_all_land(t: bt.TestCaseRun) -> None:
    fake = _board()
    t.h1("two updates on different rows + one add_todo, concurrently")
    errors = _run(lambda: log.update_todo(fake, "td-1", {"priority": 1}),
                  lambda: log.complete_todo(fake, "td-2"),
                  lambda: log.add_todo(fake, area="operations", title="new work", priority=3))
    t.tln(f"errors: {errors}")
    t.tln(f"rows: {len(fake.tables['todos'])} (3 + 1 added, no duplicates, none lost)")
    ids = {r["todo_id"] for r in fake.tables["todos"]}
    t.tln(f"unique ids: {len(ids)}")
    t.tln(f"td-1 priority={_row(fake, 'td-1')['priority']}  td-2 status={_row(fake, 'td-2')['status']}")
    t.tln(f"reads that found the table empty: {fake.table_absent_reads}")


def test_concurrent_edits_of_the_same_row_compose(t: bt.TestCaseRun) -> None:
    fake = _board()
    _pause_first_writer_until_second_has_read(fake)
    t.h1("A sets priority, B sets status; both read the same version first")
    errors = _run(lambda: log.update_todo(fake, "td-1", {"priority": 1}),
                  lambda: log.update_todo(fake, "td-1", {"status": "prog"}))
    row = _row(fake, "td-1")
    t.tln(f"errors: {errors}")
    t.tln(f"priority={row['priority']} status={row['status']} (both edits kept)")


def test_concurrent_appends_both_land(t: bt.TestCaseRun) -> None:
    fake = FakeAito([_todo("td-1", detail="base")])
    _pause_first_writer_until_second_has_read(fake)
    t.h1("two lanes append a section at the same time")
    errors = _run(lambda: log.update_todo(fake, "td-1", {}, append_detail="=== lane A ==="),
                  lambda: log.update_todo(fake, "td-1", {}, append_detail="=== lane B ==="))
    detail = _row(fake, "td-1")["detail"]
    t.tln(f"errors: {errors}")
    t.tln(f"starts with the original: {detail.startswith('base')}")
    t.tln(f"lane A kept: {'lane A' in detail}  lane B kept: {'lane B' in detail}")


def test_a_claim_race_has_one_winner(t: bt.TestCaseRun) -> None:
    fake = _board()
    _pause_first_writer_until_second_has_read(fake)
    t.h1("two agents claim the same free todo")
    errors = _run(lambda: log.claim_todo(fake, "td-1", "agent-a"),
                  lambda: log.claim_todo(fake, "td-1", "agent-b"))
    t.tln(f"exactly one owner: {_row(fake, 'td-1')['owner'] in ('agent-a', 'agent-b')}")
    t.tln(f"losers: {len(errors)}, and the loser was told why: "
          f"{all('ClaimTaken' in e for e in errors)}")


def test_success_is_the_persisted_row_not_an_echo(t: bt.TestCaseRun) -> None:
    t.h1("the engine accepts the write but applies nothing")
    fake = FakeAito([_todo("td-1", rev=log.INITIAL_REV)])   # an already-versioned row
    fake.drop_updates = True
    try:
        log.update_todo(fake, "td-1", {"detail": "a 10 KB handoff"})
        t.tln("returned success (WRONG)")
    except log.TodoWriteNotPersisted as e:
        t.tln(f"TodoWriteNotPersisted: {re.sub(r'rv-[0-9a-f]{32}', 'rv-<new>', str(e))}")
    t.tln(f"row unchanged: {_row(fake, 'td-1')['detail'] is None}")

    t.h1("a read that lags the write: retried, then the persisted row returned")
    fake = _board()
    fake.stale_reads = 2
    row = log.update_todo(fake, "td-1", {"priority": 1})
    t.tln(f"returned priority={row['priority']} rev set={bool(row['rev'])}")


def test_a_write_that_dies_midway_leaves_the_table_intact(t: bt.TestCaseRun) -> None:
    fake = _board(5)

    def die(where, set_fields):
        raise ConnectionError("read timed out")
    fake.before_update = die
    t.h1("the connection dies at the write")
    try:
        log.update_todo(fake, "td-3", {"priority": 1})
    except ConnectionError as e:
        t.tln(f"raised: {e}")
    t.tln(f"rows: {len(fake.tables['todos'])} (all 5 still there)")
    t.tln(f"td-3 unchanged: {_row(fake, 'td-3')['priority'] == 2}")


def test_the_write_path_never_rewrites_the_table(t: bt.TestCaseRun) -> None:
    fake = _board()
    t.h1("update, complete, archive, reorder, claim, append on the fake engine")
    t.tln("(FakeAito.delete_table/create_table raise if any of these touch the table)")
    log.update_todo(fake, "td-1", {"title": "renamed"})
    log.complete_todo(fake, "td-2")
    log.archive_todo(fake, "td-3")
    log.reorder_todos(fake, ["td-3", "td-1", "td-2"])
    log.claim_todo(fake, "td-1", "me")
    log.update_todo(fake, "td-1", {}, append_detail="note")
    for r in fake.tables["todos"]:
        t.tln(f"{r['todo_id']} status={r['status']} sort_order={r['sort_order']} "
              f"owner={r['owner']} title={r['title']!r}")


def test_reads_never_see_an_empty_table_during_concurrent_writes(t: bt.TestCaseRun) -> None:
    fake = _board(10)
    stop = threading.Event()
    seen = []

    def reader():
        while not stop.is_set():
            seen.append(fake.query({"from": "todos", "limit": 100})["total"])

    t.h1("a reader loops while 20 writes run on 10 rows")
    th = threading.Thread(target=reader)
    th.start()
    _run(*[(lambda i=i: log.update_todo(fake, f"td-{i % 10 + 1}", {"priority": 1 + i % 3}))
           for i in range(20)])
    stop.set()
    th.join(5)
    t.tln(f"reads: {'many' if len(seen) > 20 else len(seen)}  distinct totals seen: {sorted(set(seen))}")


# --- against a real engine ------------------------------------------------------

def test_live_concurrent_writes_on_a_real_engine(t: bt.TestCaseRun) -> None:
    """The same guarantees against a real Aito, in the suite's own dedicated,
    disposable test env (which every test reseeds). Opt-in:
    COMPANY_AI_ENV_TESTS=1, and never the shared instance."""
    config = Config.from_env()
    if os.environ.get("COMPANY_AI_ENV_TESTS") != "1" or "shared.aito.ai" in config.instance_url:
        t.tln("SKIPPED — needs COMPANY_AI_ENV_TESTS=1 and a disposable instance")
        return
    env = AitoClient(config.instance_url, config.api_key)
    loaders.create_schema(env)
    loaders.load_todos(env, SEED_DIR)
    ids = [r["todo_id"] for r in env.query({"from": "todos", "where": {"area": "operations"},
                                             "limit": 4})["hits"]]
    before = env.count("todos")
    t.h1("two updates on different rows + an add_todo, concurrently")
    errors = _run(lambda: log.update_todo(env, ids[0], {"priority": 1}),
                  lambda: log.complete_todo(env, ids[1], as_of=date(2026, 9, 27)),
                  lambda: log.add_todo(env, area="operations", title="live add", priority=3))
    t.tln(f"errors: {errors}")
    t.tln(f"row count: before + 1 = {env.count('todos') == before + 1}")
    t.h1("two concurrent appends to one todo")
    errors = _run(lambda: log.update_todo(env, ids[2], {}, append_detail="=== lane A ==="),
                  lambda: log.update_todo(env, ids[2], {}, append_detail="=== lane B ==="))
    detail = log._todo_rows(env, ids[2])[0].get("detail") or ""
    t.tln(f"errors: {errors}  both kept: {'lane A' in detail and 'lane B' in detail}")
    t.h1("two agents claim the same todo")
    errors = _run(lambda: log.claim_todo(env, ids[3], "agent-a"),
                  lambda: log.claim_todo(env, ids[3], "agent-b"))
    owner = log._todo_rows(env, ids[3])[0].get("owner")
    t.tln(f"one owner: {owner in ('agent-a', 'agent-b')}  losers: {len(errors)}")
    all_ids = {r["todo_id"] for r in env.query({"from": "todos", "limit": 100000})["hits"]}
    t.tln(f"no duplicate ids: {len(all_ids) == env.count('todos')}")
