"""Concurrent writers on routines and documents (td-20261012114045038839).

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

from company_ai import log, loaders
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
