# 26 · Remote MCP (cloud Claude over HTTP)

The MCP server (`server.py`, docs/01) is stdio by default — a local process a
desktop Claude spawns. **Remote MCP** exposes that same server over HTTP at
`https://<dashboard-host>/mcp` so **cloud** Claude (claude.ai connectors on web /
desktop / mobile, or Claude Code remote) can reach the live instance. It is the
same Claude calling the same tools — transport, not a new reasoning layer, so
rule 1 is intact and rule 2 still owns every number.

## Where it runs

Mounted **inside the dashboard app** (`api.create_app`), not a separate service:
one deployment, one port, the same prod-instance config. The dashboard already
fronts `ai.example.com` over HTTPS, so `/mcp` rides the same host.

Transport is **streamable HTTP** (the current recommended MCP transport, and
what both Claude surfaces speak). The handler is FastMCP's path-agnostic
`StreamableHTTPASGIApp`, dispatched to `/mcp` *above* FastAPI's router so bare
`/mcp` works with no trailing-slash redirect (a 307 on a POST can drop the body).

## Two guards (why public exposure is safe)

1. **Bearer token, fail-closed.** Every request must carry
   `Authorization: Bearer <COMPANY_AI_MCP_TOKEN>`; a constant-time miss returns
   401. **If the token is unset the endpoint is not mounted at all** — an
   unconfigured deploy exposes nothing. Set a strong random secret in `.env.aito`
   (`python -c "import secrets; print(secrets.token_urlsafe(40))"`); rotate by
   changing it and redeploying.
2. **Read + safe writes.** The destructive tools (`REMOTE_DENY` in
   `remotemcp.py` — `remove_document`, plus the infra tools) are stripped from the
   remote surface. The cloud agent can brief, search, log, add, and run routines,
   but never delete. The full set stays on the local stdio server, which isn't
   network-exposed.

DNS-rebinding host protection (FastMCP's localhost-only default) is relaxed: the
endpoint is public, proxy-fronted, and gated by the token, and the default would
reject the real `Host` behind the deployment's proxy. The bearer token is the
security boundary.

## Connecting

**Claude Code** (bearer is production-supported):
```
claude mcp add --transport http aito https://ai.example.com/mcp \
  --header "Authorization: Bearer <token>"
```

**claude.ai (web / desktop / mobile)** — Settings → Connectors → *Add custom
connector*, URL `https://ai.example.com/mcp`. Static-header (bearer) auth is a
**beta** connector option; if your account/org has it, paste the token there. If
only OAuth is offered, that is a larger follow-up (this server would need to add
`/authorize`, `/token`, PKCE, and RFC 9728 protected-resource metadata — the
`mcp` SDK does not ship those endpoints). See the auth matrix in the connector
docs.

## Deploying

The token lives in `.env.aito`, applied on deploy like the other prod secrets.
After `./do deploy-company-ai <tag>`, `/mcp` is live. Because a new instance /
release can change schema, remember `create-schema` against the instance too
(the deploy migrates code, not the Aito schema).

## Not built here

OAuth (for claude.ai accounts without the static-header beta) and per-user /
scoped tokens are parked — the single static token is one operator's key. Adding
OAuth is additive: the transport mount and tool surface stay; only the auth
layer changes.
