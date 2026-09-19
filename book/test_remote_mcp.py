"""Remote MCP gate (docs/26): the MCP server exposed over HTTP at /mcp for cloud
Claude, bearer-gated and trimmed to read + safe writes.

No Aito needed — the auth gate and the tool listing are protocol-level, so this
runs fast and deterministic. It proves the security contract: fail-closed when
unconfigured, 401 without the token, a working session with it, and the
destructive tools absent from the remote surface (they stay on local stdio).
"""

import dataclasses
import json

import booktest as bt
from fastapi.testclient import TestClient

from company_ai.api import create_app
from company_ai.config import Config

TOKEN = "test-mcp-token-abc123"
_HDR = {"Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json"}
_INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "booktest", "version": "1"}}}


def _cfg(token: str) -> Config:
    return dataclasses.replace(Config.from_env(), mcp_token=token)


def _json(resp) -> dict:
    body = resp.text
    if "data:" in body:                      # SSE framing → take the data line
        body = body.split("data:", 1)[1].strip()
    return json.loads(body)


def test_fail_closed_without_token(t: bt.TestCaseRun) -> None:
    t.h1("no COMPANY_AI_MCP_TOKEN → /mcp is not exposed at all (fail closed)")
    app = create_app(_cfg(""))
    with TestClient(app) as c:
        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    t.tln(f"POST /mcp with remote MCP disabled → {r.status_code} (not a 200 MCP response)")
    assert r.status_code != 200


def test_bearer_gate(t: bt.TestCaseRun) -> None:
    app = create_app(_cfg(TOKEN))
    with TestClient(app) as c:
        t.h1("the bearer gate")
        no_auth = c.post("/mcp", json=_INIT)
        wrong = c.post("/mcp", headers={"Authorization": "Bearer nope"}, json=_INIT)
        ok = c.post("/mcp", headers=_HDR, json=_INIT)
        t.tln(f"no Authorization header      → {no_auth.status_code}")
        t.tln(f"wrong token                  → {wrong.status_code}")
        t.tln(f"correct token (initialize)   → {ok.status_code}")
        t.tln(f"bare /mcp works, no redirect → {ok.status_code == 200}")
        # the dashboard is unaffected on non-/mcp paths
        t.tln(f"dashboard /api/docs still up  → {c.get('/api/docs').status_code}")
    assert no_auth.status_code == 401 and wrong.status_code == 401 and ok.status_code == 200


def test_remote_surface_is_read_plus_safe_writes(t: bt.TestCaseRun) -> None:
    app = create_app(_cfg(TOKEN))
    with TestClient(app) as c:
        init = c.post("/mcp", headers=_HDR, json=_INIT)
        sid = init.headers.get("mcp-session-id")
        h = {**_HDR, "mcp-session-id": sid}
        c.post("/mcp", headers=h, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        listed = c.post("/mcp", headers=h,
                        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = sorted(tool["name"] for tool in _json(listed)["result"]["tools"])

    t.h1("the remote tool surface (read + safe writes)")
    t.tln(f"{len(names)} tools exposed over HTTP:")
    for n in names:
        t.tln(f"  {n}")

    t.h1("destructive tools are NOT on the remote surface (stay on local stdio)")
    from company_ai.remotemcp import REMOTE_DENY
    for denied in sorted(REMOTE_DENY):
        t.tln(f"  {denied}: exposed={denied in names}")
        assert denied not in names
    # the useful safe writes ARE present
    for expected in ("add_document", "add_deal", "log_touch", "run_routine"):
        assert expected in names, f"{expected} should be on the remote surface"
