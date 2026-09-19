"""API tokens for the remote MCP (docs/28).

Named, revocable bearer tokens managed from the Admin view, as an alternative /
addition to the single env master token. Security posture:

  - Only a **SHA-256 hash** of the secret is stored (never the plaintext). The
    secret is generated server-side, shown to the operator once, and cannot be
    recovered — a leak of the tokens table does not leak usable tokens.
  - `verify()` accepts a presented token if it matches the env **master** token
    (constant-time) OR the hash of any **active** stored token. Revoking (active
    = false) takes effect on the next request — no caching.

Read/verify only here; the write path (create/revoke) is in log.py.
"""

import hashlib
import hmac

from .aito import AitoClient


def hash_token(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def list_tokens(client: AitoClient) -> list[dict]:
    """Tokens for display — label, prefix, created, active. Never the hash."""
    rows = client.query({"from": "tokens", "limit": 10000})["hits"]
    rows.sort(key=lambda r: (not r.get("active"), r.get("created", "")), reverse=False)
    return [{"token_id": r["token_id"], "label": r.get("label"),
             "prefix": r.get("prefix"), "created": r.get("created"),
             "active": r.get("active")} for r in rows]


def verify(client: AitoClient, presented: str, master: str | None = None) -> bool:
    """True if `presented` is the env master token or an active stored token.

    The env master is compared constant-time. Stored tokens are matched by the
    SHA-256 of the presented value against the active hashes (the presented value
    is hashed first, so a timing side-channel reveals nothing about the secret).
    Empty/blank never matches."""
    if not presented:
        return False
    if master and hmac.compare_digest(presented, master):
        return True
    digest = hash_token(presented)
    try:
        rows = client.query({"from": "tokens", "where": {"active": True},
                             "limit": 10000})["hits"]
    except Exception:
        return False   # tokens table absent (never provisioned) → only master works
    active = {r.get("token_hash") for r in rows}
    return any(hmac.compare_digest(digest, h) for h in active if h)
