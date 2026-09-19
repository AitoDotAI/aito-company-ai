"""Remote MCP OAuth (docs/29): the self-hosted OAuth 2.1 authorization server
that lets claude.ai's "Add custom connector" dialog authenticate to /mcp.

No Aito and no Easy Auth needed — the whole flow is protocol-level, so this runs
fast and deterministic. It proves the contract claude.ai walks through: discover
the metadata, register (DCR), get redirected through /authorize for a code,
exchange it (with PKCE) for a token, and call /mcp with it — while the existing
named/master bearer tokens (docs/28) still pass the same gate and bad tokens are
refused. Secrets (tokens, client_id, timestamps) are random, so the snapshot
records structure and outcomes, not the values.

In production /authorize sits *behind* Entra Easy Auth (the Microsoft login is
the real gate); here there is no Easy Auth, so the handler runs directly — which
is exactly the OAuth logic this test is meant to pin down.
"""

import base64
import dataclasses
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

import booktest as bt
from fastapi.testclient import TestClient

from company_ai.api import create_app
from company_ai.config import Config

MASTER = "test-mcp-token-abc123"
PUBLIC = "http://localhost:8770"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
_ACC = "application/json, text/event-stream"
_INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "booktest", "version": "1"}}}


def _cfg() -> Config:
    return dataclasses.replace(Config.from_env(), mcp_token=MASTER, public_url=PUBLIC)


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def test_discovery_metadata(t: bt.TestCaseRun) -> None:
    t.h1("OAuth discovery — the two .well-known documents claude.ai fetches first")
    app = create_app(_cfg())
    with TestClient(app) as c:
        prm = c.get("/.well-known/oauth-protected-resource/mcp")
        asm = c.get("/.well-known/oauth-authorization-server")

    t.h2("protected-resource metadata (points /mcp at its authorization server)")
    pr = prm.json()
    t.tln(f"status                 {prm.status_code}")
    t.tln(f"resource               {pr['resource']}")
    t.tln(f"authorization_servers  {pr['authorization_servers']}")

    t.h2("authorization-server metadata (the endpoint map)")
    a = asm.json()
    t.tln(f"status                    {asm.status_code}")
    for k in ("issuer", "authorization_endpoint", "token_endpoint",
              "registration_endpoint", "revocation_endpoint"):
        t.tln(f"{k:26}{a[k]}")
    t.tln(f"grant_types_supported     {a['grant_types_supported']}")
    t.tln(f"code_challenge_methods     {a['code_challenge_methods_supported']}")
    # public clients: claude.ai registers with token_endpoint_auth_method=none
    # (PKCE, no secret), so the token endpoint must advertise "none" or a strict
    # client won't attempt the exchange. Revocation stays secret-only — honest,
    # since the SDK's revoke rejects secretless clients (docs/29).
    t.tln(f"token_endpoint_auth       {a['token_endpoint_auth_methods_supported']}")
    t.tln(f"revocation_endpoint_auth  {a['revocation_endpoint_auth_methods_supported']}")
    assert prm.status_code == 200 and asm.status_code == 200
    assert a["code_challenge_methods_supported"] == ["S256"]
    assert "none" in a["token_endpoint_auth_methods_supported"]
    assert "none" not in a["revocation_endpoint_auth_methods_supported"]


def test_full_authorization_code_flow(t: bt.TestCaseRun) -> None:
    app = create_app(_cfg())
    with TestClient(app) as c:
        t.h1("1. dynamic client registration (claude.ai self-registers)")
        reg = c.post("/register", json={
            "client_name": "claude-connector",
            "redirect_uris": [REDIRECT],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none"})
        client_id = reg.json()["client_id"]
        t.tln(f"POST /register            → {reg.status_code}")
        t.tln(f"client_id issued          → {bool(client_id)}")
        t.tln(f"redirect_uris echoed      → {reg.json()['redirect_uris']}")

        t.h1("2. authorize with PKCE → 302 back to the client with a code")
        verifier, challenge = _pkce()
        authz = c.get("/authorize", params={
            "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
            "code_challenge": challenge, "code_challenge_method": "S256",
            "state": "xyz"}, follow_redirects=False)
        loc = urlparse(authz.headers.get("location", ""))
        q = parse_qs(loc.query)
        code = q.get("code", [""])[0]
        t.tln(f"GET /authorize            → {authz.status_code}")
        t.tln(f"redirect host+path        → {loc.scheme}://{loc.netloc}{loc.path}")
        t.tln(f"state preserved           → {q.get('state') == ['xyz']}")
        t.tln(f"code returned             → {bool(code)}")

        t.h1("3. exchange the code (+ PKCE verifier) for tokens")
        tok = c.post("/token", data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
            "client_id": client_id, "code_verifier": verifier})
        body = tok.json()
        access, refresh = body.get("access_token"), body.get("refresh_token")
        t.tln(f"POST /token               → {tok.status_code}")
        t.tln(f"token_type                → {body.get('token_type')}")
        t.tln(f"expires_in                → {body.get('expires_in')}")
        t.tln(f"access + refresh issued   → {bool(access) and bool(refresh)}")

        t.h1("4. wrong PKCE verifier is rejected (the code is single-use)")
        # a fresh code, exchanged with the WRONG verifier → invalid_grant
        authz2 = c.get("/authorize", params={
            "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
            "code_challenge": challenge, "code_challenge_method": "S256"},
            follow_redirects=False)
        code2 = parse_qs(urlparse(authz2.headers["location"]).query)["code"][0]
        bad = c.post("/token", data={
            "grant_type": "authorization_code", "code": code2, "redirect_uri": REDIRECT,
            "client_id": client_id, "code_verifier": "not-the-verifier"})
        t.tln(f"POST /token wrong verifier → {bad.status_code} ({bad.json().get('error')})")

        t.h1("5. call /mcp — OAuth token AND named/master token pass one gate")
        def mcp(token):
            return c.post("/mcp", json=_INIT, headers={
                "Authorization": f"Bearer {token}", "Accept": _ACC,
                "Content-Type": "application/json"}).status_code
        oauth_ok = mcp(access)
        master_ok = mcp(MASTER)
        none_401 = c.post("/mcp", json=_INIT,
                          headers={"Accept": _ACC, "Content-Type": "application/json"}).status_code
        wrong_401 = mcp("nope")
        t.tln(f"OAuth access token        → {oauth_ok}")
        t.tln(f"named/master bearer token → {master_ok}")
        t.tln(f"no token                  → {none_401}")
        t.tln(f"wrong token               → {wrong_401}")

        t.h1("6. refresh rotates the token pair")
        rt = c.post("/token", data={
            "grant_type": "refresh_token", "refresh_token": refresh, "client_id": client_id})
        new_access = rt.json().get("access_token")
        t.tln(f"POST /token (refresh)     → {rt.status_code}")
        t.tln(f"new access token issued   → {bool(new_access) and new_access != access}")

    assert authz.status_code == 302 and tok.status_code == 200
    assert bad.status_code == 400
    assert oauth_ok == 200 and master_ok == 200
    assert none_401 == 401 and wrong_401 == 401
    assert rt.status_code == 200 and new_access and new_access != access
