"""OAuth 2.1 authorization server for the remote MCP (docs/26, docs/29).

claude.ai's "Add custom connector" dialog speaks OAuth, not a bearer field: it
discovers the endpoints, registers itself (dynamic client registration), sends
the operator through an authorization redirect, and exchanges the returned code
for a token it then presents to `/mcp`. This module implements the small OAuth
*provider* the MCP SDK needs to serve that flow — the SDK owns the HTTP handlers
(`/authorize`, `/token`, `/register`, `/revoke`, the `.well-known` metadata),
PKCE verification, and the redirect_uri check; we own only storage and the
minting of codes and tokens.

The security boundary is Microsoft, not this code. `/authorize` runs *behind*
Azure Entra Easy Auth, so only someone who can sign into the tenant ever reaches
`authorize()` to receive a code — reaching the handler *is* the authorization,
which is why there is no consent screen and no per-user token binding. The other
endpoints are server-to-server (Easy-Auth-excluded) and are protected by the
OAuth machinery itself: the one-time code, PKCE, and the bearer token. The
remote surface is the same read+safe-write set for any operator the tenant
trusts — the same rationale as the named bearer tokens (docs/28), which keep
working through the same `/mcp` gate because `load_access_token` also accepts
them.

Storage is in-memory by design: clients, codes, and tokens carry no business
data and are short-lived, so they never touch Aito. The one visible cost is that
a process restart drops issued tokens — the connector then re-authorizes once (a
single click). Rule 1/2 are untouched: this is transport auth, not reasoning; no
prediction, no number lives here.
"""

import secrets
import time

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthToken

_CODE_TTL = 300              # an authorization code is valid for 5 min (RFC: short)
_TOKEN_TTL = 3600           # access-token lifetime; the refresh token renews it
_REFRESH_TTL = 30 * 24 * 3600   # refresh token lifetime (30 days)


def _new_token() -> str:
    """A 256-bit URL-safe secret — well above the RFC 6749 §10.10 minimum."""
    return secrets.token_urlsafe(32)


class OAuthProvider:
    """An in-memory ``OAuthAuthorizationServerProvider`` (the MCP SDK's Protocol).

    ``verify(token) -> bool`` recognises the env-master / named bearer tokens
    (docs/28); ``load_access_token`` consults it so Claude Code's existing tokens
    reach the same ``/mcp`` surface as OAuth-issued ones. ``now`` is injectable so
    booktests can exercise expiry deterministically.
    """

    def __init__(self, verify, now=time.time):
        self._verify = verify
        self._now = now
        self._clients: dict = {}
        self._codes: dict = {}
        self._access: dict = {}
        self._refresh: dict = {}
        self._pair: dict = {}   # token -> its sibling (access<->refresh) for revoke

    # ---- dynamic client registration -------------------------------------
    async def get_client(self, client_id):
        return self._clients.get(client_id)

    async def register_client(self, client_info):
        self._clients[client_info.client_id] = client_info

    # ---- authorization endpoint ------------------------------------------
    async def authorize(self, client, params):
        # Reaching here means the request passed Easy Auth, so this *is* the
        # authorization: mint a one-time code bound to the PKCE challenge and the
        # redirect_uri, then send the client back. The SDK verifies the PKCE
        # verifier and the redirect_uri again at /token.
        code = _new_token()
        self._codes[code] = AuthorizationCode(
            code=code,
            scopes=params.scopes or [],
            expires_at=self._now() + _CODE_TTL,
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        return construct_redirect_uri(
            str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(self, client, authorization_code):
        code = self._codes.get(authorization_code)
        if code is None or code.client_id != client.client_id:
            return None
        if code.expires_at < self._now():
            self._codes.pop(authorization_code, None)
            return None
        return code

    async def exchange_authorization_code(self, client, authorization_code):
        # one-time use: burn the code before issuing the token pair
        self._codes.pop(authorization_code.code, None)
        return self._issue(client.client_id, authorization_code.scopes)

    # ---- refresh ----------------------------------------------------------
    async def load_refresh_token(self, client, refresh_token):
        rt = self._refresh.get(refresh_token)
        if rt is None or rt.client_id != client.client_id:
            return None
        if rt.expires_at is not None and rt.expires_at < self._now():
            self._forget(refresh_token)
            return None
        return rt

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        # rotate both tokens (SDK guidance); requested scopes may only narrow —
        # they were already validated against the grant by the SDK handler.
        self._forget(refresh_token.token)
        return self._issue(client.client_id, scopes or refresh_token.scopes)

    # ---- resource-server verification (/mcp) -----------------------------
    async def load_access_token(self, token):
        at = self._access.get(token)
        if at is not None:
            if at.expires_at is not None and at.expires_at < self._now():
                self._forget(token)
                return None
            return at
        # Not an OAuth token: accept the env-master / named bearer tokens so
        # Claude Code (docs/28) reaches the same surface through this one gate.
        if self._verify(token):
            return AccessToken(
                token=token, client_id="bearer", scopes=[], expires_at=None)
        return None

    async def revoke_token(self, token):
        # revoke the presented token and its sibling (SDK: revoke both halves)
        self._forget(token.token)

    # ---- helpers ----------------------------------------------------------
    def _issue(self, client_id, scopes):
        access, refresh = _new_token(), _new_token()
        now = int(self._now())
        self._access[access] = AccessToken(
            token=access, client_id=client_id, scopes=scopes,
            expires_at=now + _TOKEN_TTL)
        self._refresh[refresh] = RefreshToken(
            token=refresh, client_id=client_id, scopes=scopes,
            expires_at=now + _REFRESH_TTL)
        self._pair[access] = refresh
        self._pair[refresh] = access
        return OAuthToken(
            access_token=access, token_type="Bearer",
            expires_in=_TOKEN_TTL, refresh_token=refresh,
            scope=" ".join(scopes) if scopes else None)

    def _forget(self, token):
        """Drop a token and its paired sibling from every store."""
        sibling = self._pair.pop(token, None)
        self._pair.pop(sibling, None)
        for t in (token, sibling):
            if t is not None:
                self._access.pop(t, None)
                self._refresh.pop(t, None)
