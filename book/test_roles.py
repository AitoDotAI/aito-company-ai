"""SDR role enforcement (docs/27 Phase 2).

The security contract: an SDR gets read + safe writes; the operator-only
operations (destructive + admin) return 403 for an SDR and pass for the
operator. Enforced by one central middleware, exercised here through the real
FastAPI app so the policy — not a mock — is what's tested. Requires a running
Aito (the app resolves identity against the users table).
"""

import booktest as bt
from fastapi.testclient import TestClient

from company_ai import loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

SDR = {"X-MS-CLIENT-PRINCIPAL-NAME": "sam@example.com"}
OPERATOR = {"X-MS-CLIENT-PRINCIPAL-NAME": "alex@example.com"}

# (label, method, path) — the operator-only surface (destructive + admin).
OPERATOR_ONLY = [
    ("delete a document", "DELETE", "/api/documents/x"),
    ("add a user", "POST", "/api/users"),
    ("edit a user", "PATCH", "/api/users/u1"),
    ("create a routine", "POST", "/api/routines"),
    ("edit a routine", "PATCH", "/api/routines/r1"),
    ("rebuild the search index", "POST", "/api/search/reindex"),
]
# safe writes an SDR may perform (403 would be wrong — anything else is fine).
SAFE_WRITES = [
    ("assign work", "POST", "/api/assignments"),
    ("tick a routine", "POST", "/api/routines/r1/tick"),
    ("add a document", "POST", "/api/documents"),
    ("edit a document", "PATCH", "/api/documents/x"),
]


def _app():
    cfg = Config.from_env()
    c = AitoClient(cfg.instance_url, cfg.api_key)
    loaders.create_schema(c)
    loaders.load_users(c, SEED_DIR)
    from company_ai.api import create_app
    return TestClient(create_app(cfg))


def _call(client, method, path, headers):
    return client.request(method, path, headers=headers, json={})


def test_operator_only_endpoints_block_the_sdr(t: bt.TestCaseRun) -> None:
    client = _app()
    t.h1("operator-only operations: 403 for the SDR, allowed for the operator")
    for label, method, path in OPERATOR_ONLY:
        sdr = _call(client, method, path, SDR).status_code
        op = _call(client, method, path, OPERATOR).status_code
        t.tln(f"  {label:28} SDR={sdr} (403)  operator={op} (not 403)")
        assert sdr == 403, f"{label}: SDR should be 403, got {sdr}"
        assert op != 403, f"{label}: operator should not be 403, got {op}"


def test_safe_writes_are_allowed_for_the_sdr(t: bt.TestCaseRun) -> None:
    client = _app()
    t.h1("safe writes are NOT blocked for the SDR (never 403)")
    for label, method, path in SAFE_WRITES:
        code = _call(client, method, path, SDR).status_code
        t.tln(f"  {label:20} SDR={code} (not 403; a 4xx/5xx here is validation, not the role gate)")
        assert code != 403, f"{label}: SDR should not be role-blocked, got {code}"


def test_unmapped_identity_is_not_operator(t: bt.TestCaseRun) -> None:
    # an authenticated Easy-Auth identity that is NOT in the users table must be
    # a guest (403 on admin), never silently promoted to operator. Also: /api/me
    # reports guest, and the raw Data sheets are operator-only.
    client = _app()
    stranger = {"X-MS-CLIENT-PRINCIPAL-NAME": "stranger@example.com"}
    t.h1("an unmapped authenticated identity is a guest, not the operator")
    t.tln(f"/api/me role: {client.get('/api/me', headers=stranger).json().get('role')}")
    for label, method, path in [("add a user", "POST", "/api/users"),
                                ("create a token", "POST", "/api/tokens"),
                                ("list tokens", "GET", "/api/tokens"),
                                ("read a raw data sheet", "GET", "/api/table")]:
        code = _call(client, method, path, stranger).status_code
        t.tln(f"  {label:22} unmapped={code} (403)")
        assert code == 403, f"{label}: unmapped identity should be 403, got {code}"

    t.h1("the tokens table is never viewable as a raw sheet, even for the operator")
    r = client.get("/api/table", params={"name": "tokens"}, headers=OPERATOR)
    t.tln(f"  GET /api/table?name=tokens (operator): {r.status_code} (not 200)")
    assert r.status_code != 200
