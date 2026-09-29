"""Public demo mode (COMPANY_AI_PUBLIC_DEMO, docs/32-public-demo.md).

The contract for anonymous visitors on a public host: they read, never write;
a read has no write side effects; the internal ops instance is refused at
startup; and a missing or failing language model is a message, not a 500.

Offline: every assertion here is answered before anything reaches Aito, so the
instance is a name that does not resolve.
"""

import dataclasses

import booktest as bt
from fastapi.testclient import TestClient

from company_ai.config import Config

DEMO_DB = "https://demo.invalid/db/company-demo"
WRITES = [
    ("add a todo", "POST", "/api/todos"),
    ("edit a todo", "PATCH", "/api/todos/td-1"),
    ("complete a todo", "POST", "/api/todos/td-1/complete"),
    ("add a contact", "POST", "/api/contacts"),
    ("save a chat", "PUT", "/api/chats/c1"),
    ("delete a chat", "DELETE", "/api/chats/c1"),
    ("record a search click", "POST", "/api/search/click"),
    ("run a routine", "POST", "/api/routines/r1/run"),
]


def _app(**overrides):
    from company_ai.api import create_app
    fields = {"instance_url": DEMO_DB, "public_demo": True, "operator_email": "", **overrides}
    cfg = dataclasses.replace(Config.from_env(), **fields)
    return TestClient(create_app(cfg))


def test_the_internal_instance_is_refused(t: bt.TestCaseRun) -> None:
    t.h1("a public demo pointed at the internal ops instance does not start")
    try:
        _app(instance_url="https://internal.aito.ai/db/aito")
        raise RuntimeError("create_app accepted the internal instance")
    except AssertionError as exc:
        t.tln(f"refused: {str(exc)[:80]}...")


def test_visitors_cannot_write(t: bt.TestCaseRun) -> None:
    client = _app()
    t.h1("every write is a 403 with a readable reason")
    for label, method, path in WRITES:
        r = client.request(method, path, json={})
        t.tln(f"  {label:22} {method:6} {path:28} -> {r.status_code} {r.json().get('error')}")
        assert r.status_code == 403 and r.json().get("public_demo") is True


def test_reads_have_no_write_side_effects(t: bt.TestCaseRun) -> None:
    client = _app()
    t.h1("/api/me says guest + public_demo; /api/chats lists nothing (no table creation)")
    me = client.get("/api/me").json()
    chats = client.get("/api/chats").json()
    t.tln(f"me: role={me['role']} public_demo={me['public_demo']}")
    t.tln(f"chats: {chats}")
    assert me["role"] == "guest" and me["public_demo"] is True
    assert chats == {"conversations": []}


def test_no_model_is_a_message_not_a_500(t: bt.TestCaseRun) -> None:
    client = _app(llm_api_key="", llm_azure_endpoint="", llm_base_url="")
    t.h1("the assistant with no model configured answers 503 with an explanation")
    r = client.post("/api/assistant/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    t.tln(f"-> {r.status_code} llm_unavailable={r.json().get('llm_unavailable')}")
    t.tln(f"   {r.json().get('error')}")
    assert r.status_code == 503 and r.json()["llm_unavailable"] is True


def test_inherited_model_keys_stay_off(t: bt.TestCaseRun) -> None:
    """The unified demos container gives every program every secret, and
    _env_first falls through empty values, so a public demo would inherit the
    grocery demo's REACT_APP_OPENAI_* key. The posture is decided in config:
    no LLM, embeddings, web tools or MCP unless COMPANY_AI_PUBLIC_DEMO_LLM=1."""
    import os
    inherited = {"COMPANY_AI_PUBLIC_DEMO": "1",
                 "REACT_APP_OPENAI_MODEL_API_KEY": "inherited-from-another-demo",
                 "OPENAI_API_KEY": "inherited-too", "COMPANY_AI_MCP_TOKEN": "inherited"}
    saved = {k: os.environ.get(k) for k in [*inherited, "COMPANY_AI_PUBLIC_DEMO_LLM"]}
    try:
        os.environ.update(inherited)
        off = Config.from_env()
        os.environ["COMPANY_AI_PUBLIC_DEMO_LLM"] = "1"
        opted_in = Config.from_env()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    t.h1("inherited keys in a public demo")
    t.tln(f"llm key: {bool(off.llm_api_key)}  embeddings: {off.embed_enabled}  "
          f"web fetch: {off.fetch_enabled}  mcp: {bool(off.mcp_token)}")
    t.tln(f"with COMPANY_AI_PUBLIC_DEMO_LLM=1 -> llm key: {bool(opted_in.llm_api_key)} "
          f"(embeddings still {opted_in.embed_enabled})")
    assert off.public_demo and not off.llm_api_key and not off.embed_enabled
    assert not off.fetch_enabled and not off.mcp_token
    assert opted_in.llm_api_key and not opted_in.embed_enabled
