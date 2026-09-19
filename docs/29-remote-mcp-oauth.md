# 29 · Remote MCP OAuth (the claude.ai connector)

claude.ai's **Add custom connector** dialog authenticates with OAuth, not a
pasted bearer field. So the remote MCP (`/mcp`, docs/26) hosts a small **OAuth
2.1 authorization server** that lets the connector discover, register, send you
through a login, and exchange the result for a token it presents to `/mcp`.

This is transport auth, not a new reasoning layer — rule 1 and rule 2 are
untouched, and no number lives in it. It sits alongside the named/master bearer
tokens (docs/28), which keep working: `/mcp` accepts **both** an OAuth-issued
token and a bearer token through one gate, so Claude Code (bearer) and the
claude.ai connector (OAuth) share the same endpoint.

## Who does what

The MCP SDK owns the HTTP handlers, PKCE verification, the redirect_uri check,
and the discovery metadata. We implement only the **provider** — storage plus
the minting of codes and tokens (`src/company_ai/mcpoauth.py`, ~150 lines). The
wiring lives in `remotemcp.build_oauth` and the dispatcher in `api.py`.

## The security boundary is Microsoft, not this code

`/authorize` runs **behind** Entra Easy Auth. An unauthenticated browser hitting
it is bounced to the Microsoft login first; only after signing into the tenant
does the request reach `authorize()`. So **reaching the handler *is* the
authorization** — there is no consent screen and no second identity system, and
that is deliberate: the remote surface is the same read+safe-write set for any
operator the tenant already trusts (the same rationale as the named tokens).

Everything else is protected by the OAuth machinery itself and is therefore
Easy-Auth-**excluded** (server-to-server or public metadata, no browser session):

| Path | Easy Auth | Why |
|------|-----------|-----|
| `/authorize` | **gated** | the Microsoft login is the real gate |
| `/token`, `/register`, `/revoke` | excluded | server-to-server; PKCE + one-time code protect them |
| `/.well-known/oauth-authorization-server` | excluded | public discovery metadata |
| `/.well-known/oauth-protected-resource/mcp` | excluded | public discovery metadata |
| `/mcp` | excluded | gated by the OAuth/bearer token, verified in-app |

## The flow (what claude.ai walks through)

1. `POST /mcp` → `401` with a `WWW-Authenticate` header pointing at the
   protected-resource metadata.
2. Fetch `/.well-known/oauth-protected-resource/mcp` → the authorization server
   (this app). Fetch `/.well-known/oauth-authorization-server` → the endpoint map.
3. `POST /register` (dynamic client registration) → a `client_id`.
4. Open `/authorize?...&code_challenge=...` in your browser → Easy Auth ensures
   you're signed in → `302` back to claude.ai with a one-time `code`.
5. `POST /token` with the code + PKCE `code_verifier` → an `access_token` (1 h)
   and a `refresh_token` (30 d).
6. `POST /mcp` with `Authorization: Bearer <access_token>` → the session runs.
   The token is refreshed via `/token` as it expires.

## Public clients (claude.ai) and the `none` auth method

claude.ai — like most MCP connectors — registers as a **public client**
(`token_endpoint_auth_method: "none"`): no client secret, PKCE only. Our provider
accepts that, but the MCP SDK's `build_metadata` hardcodes
`token_endpoint_auth_methods_supported` to the two `client_secret_*` methods and
omits `none`. A spec-compliant client that honours the metadata then won't even
attempt the (perfectly valid) secretless exchange. So `remotemcp._advertise_public_clients`
wraps `build_metadata` to add `none` to the **token** endpoint's method list.

One honest asymmetry: we do **not** add `none` to the *revocation* method list.
The SDK's `RevocationRequest.client_secret` is a required-but-nullable field, so a
public client (which sends no `client_secret` at all) is rejected there with a
`400`. Rather than advertise a method the endpoint would refuse, revocation stays
secret-only in the metadata — truthful. The practical effect: **public-client
tokens are not revocable via `/revoke`; they expire naturally** (1 h access, 30 d
refresh) or on a process restart (storage is in-memory). This is a minor SDK
limitation, not a hole — expiry bounds the exposure either way.

## Storage

In-memory by design: clients, codes, and tokens carry no business data and are
short-lived, so they never touch Aito. The one visible cost is that a **process
restart drops issued tokens** — the connector then re-authorizes once (a single
click). If that becomes annoying in practice, persisting the client + refresh
token in an Aito collection is the follow-up; it is not needed for correctness.

## Configuration

- **`COMPANY_AI_PUBLIC_URL`** — the app's public HTTPS origin
  (`https://ai.example.com`). It becomes the OAuth **issuer** and the resource-server
  base. **Empty = OAuth off**, and `/mcp` accepts only bearer tokens (docs/28) —
  a bearer-only deploy is unchanged.
- **`COMPANY_AI_MCP_TOKEN`** — still required to expose `/mcp` at all (fail
  closed). OAuth is additive on top of it.
- **Easy Auth** — add the excluded paths in the table above (all but
  `/authorize`). This is an Azure setting the operator applies; the app never
  changes its own auth config.

## Tested

`book/test_remote_mcp_oauth.py` drives the whole flow against `TestClient` (no
Easy Auth, no live Aito): discovery metadata, DCR, `/authorize`→302→code,
`/token` with PKCE, a wrong-verifier rejection, `/mcp` accepting **both** the
OAuth token and the named/master token while refusing bad/absent ones, and a
refresh rotation. Secrets are random, so the snapshot records structure and
outcomes, not values.
