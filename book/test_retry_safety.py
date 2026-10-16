"""Retrying a write must not write it twice (td-20261013085244963489).

On 2026-10-13 a log_touch hit a gateway 502 AFTER its row was inserted (in the
follow-up resequence); the agent retried and the touch was recorded twice.
Agents retry whatever an error says, so the tools absorb it:
  - an insert returns the row an earlier attempt wrote (same content, minutes ago);
  - a failure after the insert says the row IS recorded;
  - the client retries transient 5xx only on requests safe to repeat.
"""

from datetime import datetime

import booktest as bt
import requests

from company_ai import aito, engagements, log, loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key, 120)


def _seed(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_touches(client, SEED_DIR)


def test_a_retried_touch_is_recorded_once(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed(client)
    n = client.count("touches")
    args = dict(contact_id="sc002", channel="email", window=None, outcome="no_reply",
                notes="sent the pilot offer", next_action="call", next_action_due="2026-10-15")

    t.h1("The follow-up step fails after the insert")
    real = engagements.resequence
    engagements.resequence = lambda *a, **k: (_ for _ in ()).throw(
        aito.AitoError("POST /api/v2/data/_modify -> 502: Bad Gateway"))
    try:
        log.log_touch(client, **args)
    except log.RecordedButIncomplete as e:
        t.tln(str(e).replace(str(e).split()[1], "<touch_id>", 1))
    else:
        raise AssertionError("a failed follow-up was not reported")
    finally:
        engagements.resequence = real

    t.h1("The agent retries")
    again = log.log_touch(client, **args)
    t.tln(f"already_recorded: {again.get('already_recorded')}")
    t.tln(f"touches: {n} before, {client.count('touches')} after")
    assert again.get("already_recorded") and client.count("touches") == n + 1

    t.h1("A different engagement is still recorded")
    other = log.log_touch(client, **{**args, "notes": "a second, different mail"})
    t.tln(f"already_recorded: {other.get('already_recorded')}; touches: {client.count('touches')}")
    assert not other.get("already_recorded") and client.count("touches") == n + 2


def test_a_retried_todo_and_document_are_recorded_once(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_todos(client, SEED_DIR)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)
    todos, docs = client.count("todos"), client.count("documents")
    first = log.add_todo(client, "rnd", "Retry-safe ticket", 2, role="aito-company-ai")
    second = log.add_todo(client, "rnd", "Retry-safe ticket", 2, role="aito-company-ai")
    t.h1("add_todo twice")
    t.tln(f"same row: {first['todo_id'] == second['todo_id']}, "
          f"already_recorded: {second.get('already_recorded')}, todos +{client.count('todos') - todos}")
    assert first["todo_id"] == second["todo_id"] and client.count("todos") == todos + 1
    a = log.add_document(client, "Call notes", "Agreed a pilot.")
    b = log.add_document(client, "Call notes", "Agreed a pilot.")
    c = log.add_document(client, "Call notes", "A different call.")
    t.h1("add_document: twice the same, once different")
    t.tln(f"same row: {a['doc_id'] == b['doc_id']}, different body is new: {c['doc_id'] != a['doc_id']}, "
          f"documents +{client.count('documents') - docs}")
    assert a["doc_id"] == b["doc_id"] and client.count("documents") == docs + 2


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code, self._payload, self.text = status, payload or {}, "Bad Gateway"

    def json(self):
        return self._payload


def test_only_repeatable_requests_are_retried(t: bt.TestCaseRun) -> None:
    calls = []
    real, sleep = aito._SESSION.request, aito.time.sleep

    def flaky(method, url, **kw):
        calls.append(url.rsplit("/api/", 1)[-1])
        return _Resp(502) if len(calls) == 1 else _Resp(200, {"ok": True})
    aito._SESSION.request, aito.time.sleep = flaky, lambda s: None
    try:
        c = AitoClient("http://aito.invalid/db/x")
        c._request("POST", "/api/v2/data/_modify", {"update": "t", "where": {"id": "1"}, "set": {"v": 1}})
        t.h1("A _modify update after one 502")
        t.tln(f"attempts: {len(calls)} -> succeeded")
        calls.clear()
        try:
            c._request("POST", "/api/v2/data/t/batch", [{"id": "1"}])
        except aito.AitoError as e:
            t.h1("A batch insert after one 502")
            t.tln(f"attempts: {len(calls)} -> raised: {str(e)[:60]}")
        else:
            raise AssertionError("an insert was retried")
    finally:
        aito._SESSION.request, aito.time.sleep = real, sleep
