# 28 · API tokens (remote MCP)

Named, revocable bearer tokens for connecting cloud Claude to the remote MCP
(`/mcp`, docs/26), managed from the operator-only **Admin** view. They sit
alongside the single env **master** token (`COMPANY_AI_MCP_TOKEN`): the master
enables the endpoint and always works; named tokens are per-connector
(claude.ai for you, another for a teammate) and can be revoked without a
redeploy.

## Security posture

- **Hash-at-rest.** The secret is generated server-side (`secrets.token_urlsafe`),
  returned to the operator **once**, and only its **SHA-256 hash** (+ a short
  prefix + label) is stored in the `tokens` collection. A leak of that table
  does not leak usable tokens; a lost token is revoked and re-minted, never
  recovered.
- **Verification** (`tokens.verify`): a presented token passes if it equals the
  env master (constant-time `hmac.compare_digest`) or its SHA-256 is among the
  **active** stored hashes. The presented value is hashed before comparison, so
  timing reveals nothing about the secret. Empty never matches.
- **Immediate revoke.** `verify` queries active hashes per request (no cache),
  so revoking (`active=false`) takes effect on the next call.
- **Operator-only.** All token endpoints (list included — even labels/prefixes
  are admin) are gated by the role middleware (`api._OPERATOR_ONLY`, docs/27).
- **Fail-closed.** `/mcp` is still mounted only when the env master token is
  set; named tokens are additive, never a way to open an otherwise-closed
  endpoint.

## Surfaces

- **Admin → Remote MCP tokens**: list (label · prefix… · created · active),
  create (the secret is shown once in a copy box), revoke.
- **API** (operator-only): `GET /api/tokens` (never the hash), `POST /api/tokens`
  (returns the plaintext once), `DELETE /api/tokens/{id}` (revoke).
- **Store**: the `tokens` collection is app-state — created by `create-schema`,
  never seeded/exported, and (holding real secret hashes) never in the repo.

## Not built

Per-token scopes/expiry and last-used tracking are parked. The remote surface is
already fenced to read + safe writes for *all* tokens (`remotemcp.REMOTE_DENY`);
a future refinement could scope a token to a subset or expire it. Last-used
would mean a write per request — deferred rather than pay that cost.
