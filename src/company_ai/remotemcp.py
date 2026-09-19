"""Remote MCP (docs/26): the stdio MCP server (server.py) exposed over HTTP for
cloud Claude, mounted at `/mcp` on the dashboard app.

Two guards make public exposure safe:

  1. **Bearer token, fail-closed.** Every request must carry
     `Authorization: Bearer <COMPANY_AI_MCP_TOKEN>`; a constant-time miss returns
     401. If the token is unset the endpoint is not mounted at all (api.py), so
     an unconfigured deploy exposes nothing.
  2. **Read + safe writes.** The destructive tools are removed from the remote
     surface (`REMOTE_DENY`) — the cloud agent can brief, search, log, add, and
     run routines, but never delete. The full set stays on the local stdio
     server (`company-ai-mcp`), which isn't network-exposed.

Rule 1 is intact: this is transport, not a new reasoning layer — the same Claude
calling the same tools, now over HTTPS instead of stdio. Rule 2 still owns every
number (the tools are the same Aito-backed queries).
"""

from mcp.server.auth import routes as _auth_routes
from mcp.server.auth.provider import ProviderTokenVerifier
from mcp.server.auth.settings import (
    AuthSettings,
    ClientRegistrationOptions,
    RevocationOptions,
)
from mcp.server.fastmcp.server import StreamableHTTPASGIApp
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse

from .mcpoauth import OAuthProvider
from .server import mcp

# Paths the OAuth-enabled MCP Starlette app owns (the SDK registers these at
# absolute paths). api.py routes them to the MCP app ahead of the SPA catch-all.
# `/authorize` stays *behind* Easy Auth (the Microsoft login is the gate); the
# rest are Easy-Auth-excluded server-to-server / public-metadata endpoints.
OAUTH_PATHS = [
    "/authorize", "/token", "/register", "/revoke",
    "/.well-known/oauth-authorization-server",
    "/.well-known/oauth-protected-resource",
]

# Tools kept OFF the remote surface (they stay on the local stdio server). This
# mirrors the API's operator-only set (docs/27 role_guard): the remote agent —
# which any valid token drives and which prompt injection can steer — must not
# delete or run infra/admin.
REMOTE_DENY = {
    "remove_document",                          # destructive deletes
    "create_backup",                            # infra — backup rotation deletes restore points
    "reindex_search",                           # infra — drops/rebuilds the index
}


class BearerAuth:
    """ASGI middleware: require a valid `Authorization: Bearer <token>` before the
    wrapped app runs. `verify(token) -> bool` decides validity (the env master
    token or an active named token — see tokens.verify). Non-HTTP scopes
    (lifespan) pass straight through so the session manager still starts."""

    def __init__(self, app, verify):
        self.app = app
        self._verify = verify

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        auth = headers.get(b"authorization", b"").decode()
        token = auth[7:] if auth[:7].lower() == "bearer " else ""
        if not self._verify(token):
            response = JSONResponse(
                {"error": "unauthorized"}, status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="aito-company-ai"'})
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)


def _harden():
    """Shared setup for both build paths: drop the destructive tools and relax
    DNS-rebinding host protection (this endpoint is public, proxy-fronted, and
    bearer/OAuth-gated — the localhost-only default would reject the real Host
    header behind the deployment's proxy)."""
    for name in REMOTE_DENY:
        try:
            mcp._tool_manager.remove_tool(name)
        except Exception:
            pass  # already absent — nothing to remove
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False)
    # clear any auth left on the shared instance from a prior build (tests build
    # several) so each build starts from a known state.
    mcp.settings.auth = None
    mcp._auth_server_provider = None
    mcp._token_verifier = None
    # a session manager can only be `run()` once, so build a fresh one per app
    # (prod builds one; tests build several) — reset the lazy cache first.
    mcp._session_manager = None


def _advertise_public_clients():
    """Make the discovery metadata advertise the "none" token-endpoint auth
    method (public clients). The SDK hardcodes
    `token_endpoint_auth_methods_supported` to the two `client_secret_*` methods
    and omits "none", but claude.ai — like most MCP connectors — registers as a
    *public* client (`token_endpoint_auth_method="none"`, PKCE, no secret), which
    our provider already accepts. A spec-compliant client that honours the
    metadata won't attempt an exchange whose auth method isn't listed, so we wrap
    the SDK's module-level `build_metadata` to add "none" to the **token**
    endpoint's method list. Idempotent (guarded), applied before
    `streamable_http_app()` builds the routes so the wrapped version is used.

    We deliberately do NOT add "none" to the *revocation* method list: the SDK's
    `RevocationRequest.client_secret` is a required-but-nullable field, so a
    public client (which sends no `client_secret` at all) gets a 400 there. Rather
    than advertise a method that endpoint would reject, we leave revocation as
    secret-only — honest metadata. Public-client tokens simply expire (1 h access
    / 30 d refresh) instead of being revocable (docs/29)."""
    if getattr(_auth_routes.build_metadata, "_public_patched", False):
        return
    _orig = _auth_routes.build_metadata

    def _patched(*args, **kwargs):
        md = _orig(*args, **kwargs)
        vals = list(md.token_endpoint_auth_methods_supported or [])
        if "none" not in vals:
            md.token_endpoint_auth_methods_supported = [*vals, "none"]
        return md

    _patched._public_patched = True
    _auth_routes.build_metadata = _patched


def build(verify):
    """Build the bearer-only remote MCP ASGI app (docs/26). Removes the
    destructive tools and wraps the MCP stream handler in the bearer gate
    (`verify(token) -> bool`). Returns (session_manager, guarded_app, owned):
    the caller routes the `owned` path prefixes to `guarded_app` and runs the
    session manager as the app lifespan so the streaming transport starts.

    We mount the raw `StreamableHTTPASGIApp` (not the Starlette wrapper): it is
    path-agnostic, so both `/mcp` and `/mcp/` work with no trailing-slash
    redirect (a 307 on a POST could drop the body for some clients)."""
    _harden()
    mcp.streamable_http_app()          # (re)builds the session manager with the settings
    raw = StreamableHTTPASGIApp(mcp._session_manager)
    return mcp.session_manager, BearerAuth(raw, verify), ["/mcp"]


def build_oauth(verify, public_url):
    """Build the OAuth-enabled remote MCP app (docs/29) for claude.ai's connector.

    `public_url` is the app's public HTTPS origin (e.g. https://ai.example.com); it
    becomes the OAuth issuer and the resource-server base. The SDK serves the flow
    endpoints (see OAUTH_PATHS) and guards `/mcp` with its bearer middleware,
    which verifies tokens through the provider's `load_access_token` — accepting
    both OAuth-issued tokens AND the env-master / named bearer tokens
    (`verify`, docs/28), so Claude Code keeps working through the same gate.

    Returns (session_manager, app, owned): `app` is the SDK's Starlette app
    (auth routes + guarded `/mcp`); `owned` is the set of path prefixes the caller
    must route to it ahead of the SPA. No BearerAuth wrapper here — the SDK's
    RequireAuthMiddleware is the gate."""
    _harden()
    _advertise_public_clients()
    provider = OAuthProvider(verify)
    issuer = public_url.rstrip("/")
    mcp.settings.auth = AuthSettings(
        issuer_url=issuer,
        resource_server_url=f"{issuer}/mcp",
        # dynamic client registration on — claude.ai self-registers; no scopes
        # required, so any authenticated token (OAuth or named) passes.
        client_registration_options=ClientRegistrationOptions(enabled=True),
        revocation_options=RevocationOptions(enabled=True),
        required_scopes=[],
    )
    mcp._auth_server_provider = provider
    mcp._token_verifier = ProviderTokenVerifier(provider)
    app = mcp.streamable_http_app()    # builds session manager + auth routes + /mcp gate
    return mcp.session_manager, app, ["/mcp", *OAUTH_PATHS]
