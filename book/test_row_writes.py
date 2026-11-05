"""Concurrent writers on the app-state tables (td-20261012114045038839).

These tables used to be written by reading every row, dropping the table,
recreating it and uploading everything back. Two writers at once then race:
one's rewrite erases the other's change, or both uploads land and the table
doubles, and a reader in between sees an empty or missing table. That is how
the todos board lost rows on 2026-09-26 and how documents failed in production
on 2026-10-07 ("documents rewrite row-count mismatch").

Each test starts several writers on DIFFERENT rows at the same moment, then
checks that every write landed and that no row was lost or duplicated.
"""

import json
import threading
from datetime import date

import booktest as bt

from company_ai import log, loaders, schema
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key, 120)


def _together(calls: list) -> list:
    """Run the calls at the same moment, one thread each. Returns per call
    either its result or the exception it raised."""
    start = threading.Barrier(len(calls))
    out: list = [None] * len(calls)

    def run(i, fn):
        start.wait()
        try:
            out[i] = fn()
        except Exception as e:  # noqa: BLE001 — reported by the test
            out[i] = e
    threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(calls)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    return out


def _ids(client: AitoClient, table: str, key: str) -> list[str]:
    return sorted(r[key] for r in client.query({"from": table, "limit": 100000})["hits"])


def test_concurrent_routine_writes_all_land(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_routines(client, SEED_DIR)
    before = _ids(client, "routines", "routine_id")
    t.h1("Routines before")
    t.tln(f"{len(before)} rows: {before}")

    day = date(2026, 9, 21)
    targets = before[:4]
    calls = [lambda rid=rid: log.tick_routine(_client(), rid, as_of=day) for rid in targets[:3]]
    calls.append(lambda: log.update_routine(_client(), targets[3], {"notes": "edited concurrently"}))
    results = _together(calls)
    t.h1("Four writers at once (three ticks, one edit)")
    for rid, r in zip(targets, results):
        t.tln(f"{rid}: {'ERROR ' + type(r).__name__ + ': ' + str(r)[:120] if isinstance(r, Exception) else 'ok'}")

    after = {r["routine_id"]: r for r in client.query({"from": "routines", "limit": 100000})["hits"]}
    ids = _ids(client, "routines", "routine_id")
    t.h1("Routines after")
    t.tln(f"{len(ids)} rows")
    for rid in targets[:3]:
        t.tln(f"{rid} last_done={after.get(rid, {}).get('last_done')}")
    t.tln(f"{targets[3]} notes={after.get(targets[3], {}).get('notes')!r}")
    assert ids == before, f"rows lost or duplicated: {before} -> {ids}"
    assert not any(isinstance(r, Exception) for r in results), "a writer failed"
    assert all(after[rid].get("last_done") == day.isoformat() for rid in targets[:3]), "a tick was lost"
    assert after[targets[3]].get("notes") == "edited concurrently", "the edit was lost"


def test_concurrent_document_writes_all_land(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)
    before = _ids(client, "documents", "doc_id")
    t.h1("Documents before")
    t.tln(f"{len(before)} rows")

    edit, gone = before[:3], before[3]
    calls = [lambda d=d: log.update_document(_client(), d, {"topics": "edited-concurrently"})
             for d in edit]
    calls.append(lambda: log.delete_document(_client(), gone))
    results = _together(calls)
    t.h1("Four writers at once (three edits, one delete)")
    for d, r in zip(edit + [gone], results):
        t.tln(f"{d}: {'ERROR ' + type(r).__name__ + ': ' + str(r)[:120] if isinstance(r, Exception) else 'ok'}")

    rows = {r["doc_id"]: r for r in client.query({"from": "documents", "limit": 100000})["hits"]}
    ids = _ids(client, "documents", "doc_id")
    t.h1("Documents after")
    t.tln(f"{len(ids)} rows")
    t.tln(json.dumps({d: rows.get(d, {}).get("topics") for d in edit}))
    t.tln(f"{gone} present: {gone in rows}")
    assert ids == sorted(set(before) - {gone}), f"rows lost or duplicated: {len(before)} -> {len(ids)}"
    assert not any(isinstance(r, Exception) for r in results), "a writer failed"
    assert all(rows[d].get("topics") == "edited-concurrently" for d in edit), "an edit was lost"


def test_concurrent_post_results_all_land(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    for load in (loaders.load_materials, loaders.load_channels, loaders.load_posts):
        load(client, SEED_DIR)
    before = _ids(client, "posts", "post_id")
    t.h1("Posts before")
    t.tln(f"{len(before)} rows")

    targets = before[:3]
    days = ["2026-10-05", "2026-10-06", "2026-10-07"]
    calls = [lambda pid=pid, day=day, i=i: log.log_post_result(
                 _client(), pid, outcome="modest", reach_or_views=500 + i, posted_at=day)
             for i, (pid, day) in enumerate(zip(targets, days))]
    results = _together(calls)
    t.h1("Three post results logged at once")
    for pid, r in zip(targets, results):
        t.tln(f"{pid}: {'ERROR ' + type(r).__name__ + ': ' + str(r)[:120] if isinstance(r, Exception) else 'ok'}")

    after = {r["post_id"]: r for r in client.query({"from": "posts", "limit": 100000})["hits"]}
    ids = _ids(client, "posts", "post_id")
    t.h1("Posts after")
    t.tln(f"{len(ids)} rows")
    for pid in targets:
        r = after.get(pid, {})
        t.tln(f"{pid} posted_at={r.get('posted_at')} weekday={r.get('weekday')} "
              f"reach={r.get('reach_or_views')} won={r.get('won')}")
    assert ids == before, f"rows lost or duplicated: {len(before)} -> {len(ids)}"
    assert not any(isinstance(r, Exception) for r in results), "a writer failed"
    assert [after[pid]["posted_at"] for pid in targets] == days, "a post result was lost"


def _outcomes(t: bt.TestCaseRun, names: list, results: list) -> None:
    for name, r in zip(names, results):
        t.tln(f"{name}: {'ERROR ' + type(r).__name__ + ': ' + str(r)[:120] if isinstance(r, Exception) else 'ok'}")


def test_concurrent_experiment_results_all_land(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_experiments(client, SEED_DIR)
    before = _ids(client, "experiments", "experiment_id")
    t.h1("Experiments before")
    t.tln(f"{len(before)} rows")

    targets = before[:3]
    calls = [lambda e=e, i=i: log.log_experiment_result(
                 _client(), e, "inconclusive", 0.5 + i, learning=f"concurrent {i}",
                 as_of=date(2026, 10, 1))
             for i, e in enumerate(targets)]
    results = _together(calls)
    t.h1("Three results logged at once")
    _outcomes(t, targets, results)

    after = {r["experiment_id"]: r for r in client.query({"from": "experiments", "limit": 100000})["hits"]}
    ids = _ids(client, "experiments", "experiment_id")
    t.h1("Experiments after")
    t.tln(f"{len(ids)} rows")
    for e in targets:
        r = after.get(e, {})
        t.tln(f"{e} status={r.get('status')} result={r.get('result')} learning={r.get('learning')!r} "
              f"decided={r.get('decided')} validated={r.get('validated')}")
    assert ids == before, f"rows lost or duplicated: {len(before)} -> {len(ids)}"
    assert not any(isinstance(r, Exception) for r in results), "a writer failed"
    assert [after[e].get("learning") for e in targets] == [f"concurrent {i}" for i in range(3)], \
        "a result was lost"


def test_concurrent_event_decisions_all_land(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_events(client, SEED_DIR)
    before = _ids(client, "events", "event_id")
    t.h1("Events before")
    t.tln(f"{len(before)} rows")

    targets = before[:3]
    decisions = [("go", None), ("no_go", None), ("attended", "worthwhile")]
    calls = [lambda ev=ev, s=s, o=o: log.decide_event(_client(), ev, s, outcome=o,
                                                     notes=f"decided {s}", as_of=date(2026, 10, 1))
             for ev, (s, o) in zip(targets, decisions)]
    calls.append(lambda: log.add_event(_client(), "Concurrent meetup", "meetup", "2026-12-01"))
    results = _together(calls)
    t.h1("Three decisions and one new event at once")
    _outcomes(t, targets + ["add_event"], results)

    rows = client.query({"from": "events", "limit": 100000})["hits"]
    after = {r["event_id"]: r for r in rows}
    t.h1("Events after")
    t.tln(f"{len(rows)} rows")
    for ev in targets:
        r = after.get(ev, {})
        t.tln(f"{ev} status={r.get('status')} decided={r.get('decided')} "
              f"outcome={r.get('outcome')} notes={r.get('notes')!r}")
    added = [r for r in rows if r.get("name") == "Concurrent meetup"]
    t.tln(f"new event present: {len(added)}")
    assert not any(isinstance(r, Exception) for r in results), "a writer failed"
    assert sorted(set(after) - {r["event_id"] for r in added}) == before and len(added) == 1, \
        f"rows lost or duplicated: {len(before)} -> {len(rows)}"
    assert [after[ev]["status"] for ev in targets] == [s for s, _ in decisions], "a decision was lost"


def test_concurrent_user_writes_all_land(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_users(client, SEED_DIR)
    before = _ids(client, "users", "user_id")
    t.h1("Users before")
    t.tln(f"{len(before)} rows: {before}")

    calls = [lambda u=u: log.update_user(_client(), u, {"name": f"Renamed {u}"}) for u in before]
    calls.append(lambda: log.add_user(_client(), "Casey Lee", "casey@example.com"))
    results = _together(calls)
    t.h1("Two edits and one new user at once")
    _outcomes(t, before + ["add_user"], results)

    rows = client.query({"from": "users", "limit": 100000})["hits"]
    after = {r["user_id"]: r for r in rows}
    t.h1("Users after")
    t.tln(f"{len(rows)} rows")
    for u in before:
        t.tln(f"{u} name={after.get(u, {}).get('name')!r}")
    added = [r for r in rows if r.get("email") == "casey@example.com"]
    t.tln(f"new user present: {len(added)}")
    assert not any(isinstance(r, Exception) for r in results), "a writer failed"
    assert len(rows) == len(before) + 1 and len(added) == 1, f"rows lost or duplicated: {len(rows)}"
    assert all(after[u]["name"] == f"Renamed {u}" for u in before), "an edit was lost"


def test_concurrent_assignments_all_land(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_users(client, SEED_DIR)
    loaders.load_todos(client, SEED_DIR)
    client.delete_table("assignments")
    client.create_table("assignments", schema.ASSIGNMENTS)
    todos = _ids(client, "todos", "todo_id")[:4]
    # one item already assigned, to be reassigned in the race
    log.set_assignment(client, "todos", todos[3], "u_sdr")
    t.h1("Assignments before")
    t.tln(f"{client.count('assignments')} rows")

    calls = [lambda td=td: log.set_assignment(_client(), "todos", td, "u_sdr") for td in todos[:3]]
    calls.append(lambda: log.set_assignment(_client(), "todos", todos[3], "u_operator"))
    results = _together(calls)
    t.h1("Three assignments and one reassignment at once")
    _outcomes(t, todos, results)

    rows = client.query({"from": "assignments", "limit": 100000})["hits"]
    owners = {}
    for r in rows:
        owners.setdefault(r["entity_id"], []).append(r["user_id"])
    t.h1("Assignments after")
    t.tln(f"{len(rows)} rows")
    for td in todos:
        t.tln(f"{td} -> {owners.get(td)}")
    assert not any(isinstance(r, Exception) for r in results), "a writer failed"
    assert {td: owners.get(td) for td in todos} == {
        **{td: ["u_sdr"] for td in todos[:3]}, todos[3]: ["u_operator"]}, owners

    log.set_assignment(client, "todos", todos[0], None)
    t.h1("Unassigning one")
    left = client.query({"from": "assignments", "where": {"entity_id": todos[0]}, "limit": 10})["hits"]
    t.tln(f"{todos[0]} rows left: {len(left)}; total {client.count('assignments')}")
    assert not left and client.count("assignments") == 3
    client.delete_table("assignments")
    client.create_table("assignments", schema.ASSIGNMENTS)


def test_concurrent_token_writes_all_land(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    client.delete_table("tokens")
    client.create_table("tokens", schema.TOKENS)
    made = [log.add_token(client, f"book token {i}")["token_id"] for i in range(3)]
    t.h1("Tokens before")
    t.tln(f"{client.count('tokens')} rows, all active")

    calls = [lambda tok=tok: log.revoke_token(_client(), tok) for tok in made[:2]]
    calls.append(lambda: log.add_token(_client(), "book token added in the race"))
    results = _together(calls)
    t.h1("Two revokes and one new token at once")
    _outcomes(t, ["revoke 0", "revoke 1", "add_token"], results)

    rows = {r["token_id"]: r for r in client.query({"from": "tokens", "limit": 100000})["hits"]}
    t.h1("Tokens after")
    t.tln(f"{len(rows)} rows")
    for i, tok in enumerate(made):
        t.tln(f"token {i} active={rows.get(tok, {}).get('active')}")
    assert not any(isinstance(r, Exception) for r in results), "a writer failed"
    assert len(rows) == 4, f"rows lost or duplicated: {len(rows)}"
    assert [rows[tok]["active"] for tok in made] == [False, False, True], "a revoke was lost"
    client.delete_table("tokens")
    client.create_table("tokens", schema.TOKENS)


def test_concurrent_chat_saves_all_land(t: bt.TestCaseRun) -> None:
    from company_ai import chats
    client = _client()
    client.delete_table("chat_messages")
    client.create_table("chat_messages", schema.CHAT_MESSAGES)
    msg = lambda text: [{"role": "user", "content": text}, {"role": "assistant", "content": "ok"}]
    chats.save_chat(client, "c-keep", "Left alone", msg("untouched"), 1)
    chats.save_chat(client, "c-edit", "Edited", msg("first") + msg("second"), 1)
    t.h1("Chats before")
    t.tln(f"{client.count('chat_messages')} messages in 2 conversations")

    calls = [lambda: chats.save_chat(_client(), "c-edit", "Edited", msg("shorter"), 2),
             lambda: chats.save_chat(_client(), "c-new-a", "New A", msg("a"), 2),
             lambda: chats.save_chat(_client(), "c-new-b", "New B", msg("b"), 2)]
    results = _together(calls)
    t.h1("One replace and two new conversations at once")
    _outcomes(t, ["c-edit", "c-new-a", "c-new-b"], results)

    t.h1("Chats after")
    got = {cid: [m["content"] for m in (chats.get_chat(client, cid) or {}).get("msgs", [])]
           for cid in ("c-keep", "c-edit", "c-new-a", "c-new-b")}
    for cid, contents in got.items():
        t.tln(f"{cid}: {contents}")
    t.tln(f"{client.count('chat_messages')} messages")
    assert not any(isinstance(r, Exception) for r in results), "a writer failed"
    assert got == {"c-keep": ["untouched", "ok"], "c-edit": ["shorter", "ok"],
                   "c-new-a": ["a", "ok"], "c-new-b": ["b", "ok"]}, got
    client.delete_table("chat_messages")
    client.create_table("chat_messages", schema.CHAT_MESSAGES)
