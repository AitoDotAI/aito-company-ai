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

Storage: clients, codes and tokens carry no business data, so they never touch
Aito. By default they live in memory, and a process restart drops every issued
token. That turned out to cost more than "one click": the connector does not say
it was logged out, it just stops working (the 2026-10-09/10 restarts on Azure).
So with a `state_path` (COMPANY_AI_OAUTH_STATE, docs/29) the registered clients
and the access/refresh tokens are kept in a JSON file, written atomically with
mode 0600 on every change. Tokens are stored as SHA-256 hashes, never as the
secret itself (the same rule as named tokens, docs/28): a leaked file cannot be
replayed against /mcp. Authorization codes stay in memory; they live minutes.
Rule 1/2 are untouched: this is transport auth, not reasoning; no prediction, no
number lives here.
"""

import hashlib
import json
import logging
import os
import secrets
import tempfile
import time

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

_CODE_TTL = 300              # an authorization code is valid for 5 min (RFC: short)
_TOKEN_TTL = 3600           # access-token lifetime; the refresh token renews it
_REFRESH_TTL = 30 * 24 * 3600   # refresh token lifetime (30 days)


def _new_token() -> str:
    """A 256-bit URL-safe secret — well above the RFC 6749 §10.10 minimum."""
    return secrets.token_urlsafe(32)


def _hash(token: str) -> str:
    """How a token is keyed, in memory and on disk: never the secret itself."""
    return hashlib.sha256(token.encode()).hexdigest()


_STATE_VERSION = 1
log = logging.getLogger(__name__)


class OAuthProvider:
    """An ``OAuthAuthorizationServerProvider`` (the MCP SDK's Protocol).

    ``verify(token) -> bool`` recognises the env-master / named bearer tokens
    (docs/28); ``load_access_token`` consults it so Claude Code's existing tokens
    reach the same ``/mcp`` surface as OAuth-issued ones. ``now`` is injectable so
    booktests can exercise expiry deterministically. ``state_path`` keeps clients
    and hashed tokens in a file across restarts; None keeps them in memory.

    The token stores are keyed by ``_hash(token)`` and hold the token object with
    its ``token`` field set to that hash; a lookup hands back a copy carrying the
    token the caller presented. So nothing held in memory or on disk is a usable
    secret once the response that issued it has been sent.
    """

    def __init__(self, verify, now=time.time, state_path=None):
        self._verify = verify
        self._now = now
        self._path = state_path
        self._clients: dict = {}
        self._codes: dict = {}
        self._access: dict = {}    # hash -> AccessToken(token=hash)
        self._refresh: dict = {}   # hash -> RefreshToken(token=hash)
        self._pair: dict = {}      # hash -> its sibling's hash (access<->refresh), for revoke
        if self._path:
            self._load()

    # ---- dynamic client registration -------------------------------------
    async def get_client(self, client_id):
        return self._clients.get(client_id)

    async def register_client(self, client_info):
        self._clients[client_info.client_id] = client_info
        self._save()

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
        rt = self._refresh.get(_hash(refresh_token))
        if rt is None or rt.client_id != client.client_id:
            return None
        if rt.expires_at is not None and rt.expires_at < self._now():
            self._save()           # prunes the expired entries
            return None
        return rt.model_copy(update={"token": refresh_token})

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        # rotate both tokens (SDK guidance); requested scopes may only narrow —
        # they were already validated against the grant by the SDK handler.
        self._forget(refresh_token.token)
        return self._issue(client.client_id, scopes or refresh_token.scopes)

    # ---- resource-server verification (/mcp) -----------------------------
    async def load_access_token(self, token):
        at = self._access.get(_hash(token))
        if at is not None:
            if at.expires_at is not None and at.expires_at < self._now():
                # drop THIS token only. Forgetting its pair here (as revoke
                # does) deleted the still-valid refresh token, so a connector
                # presenting an expired access token could no longer refresh
                # and had to sign in again.
                self._save()       # prunes the expired entries
                return None
            return at.model_copy(update={"token": token})
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
        ha, hr = _hash(access), _hash(refresh)
        now = int(self._now())
        self._access[ha] = AccessToken(
            token=ha, client_id=client_id, scopes=scopes,
            expires_at=now + _TOKEN_TTL)
        self._refresh[hr] = RefreshToken(
            token=hr, client_id=client_id, scopes=scopes,
            expires_at=now + _REFRESH_TTL)
        self._pair[ha] = hr
        self._pair[hr] = ha
        self._save()
        return OAuthToken(
            access_token=access, token_type="Bearer",
            expires_in=_TOKEN_TTL, refresh_token=refresh,
            scope=" ".join(scopes) if scopes else None)

    def _forget(self, token):
        """Drop a token (given as the secret) and its paired sibling from every store."""
        h = _hash(token)
        sibling = self._pair.pop(h, None)
        self._pair.pop(sibling, None)
        for t in (h, sibling):
            if t is not None:
                self._access.pop(t, None)
                self._refresh.pop(t, None)
        self._save()

    # ---- persistence (COMPANY_AI_OAUTH_STATE) -----------------------------
    def _prune(self):
        """Drop expired tokens (and their pairs), and clients whose secret expired."""
        now = self._now()
        for store in (self._access, self._refresh):
            for h, tok in list(store.items()):
                if tok.expires_at is not None and tok.expires_at < now:
                    del store[h]
        live = self._access.keys() | self._refresh.keys()
        self._pair = {a: b for a, b in self._pair.items() if a in live and b in live}
        self._clients = {
            cid: c for cid, c in self._clients.items()
            if not (c.client_secret_expires_at and c.client_secret_expires_at < now)}

    def _load(self):
        """Read the state file. A missing file is a first start; a file that
        cannot be read is an error naming the path (rule 3). Starting empty
        instead would silently log every connector out: the bug this exists for."""
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                state = json.load(f)
            assert state.get("version") == _STATE_VERSION, \
                f"unknown state version {state.get('version')!r}"
            self._clients = {c["client_id"]: OAuthClientInformationFull.model_validate(c)
                             for c in state["clients"]}
            self._access = {h: AccessToken.model_validate({**t, "token": h})
                            for h, t in state["access"].items()}
            self._refresh = {h: RefreshToken.model_validate({**t, "token": h})
                             for h, t in state["refresh"].items()}
            self._pair = dict(state["pair"])
        except Exception as e:
            raise RuntimeError(
                f"cannot read the OAuth state file {self._path} "
                f"(COMPANY_AI_OAUTH_STATE): {type(e).__name__}: {e}") from e
        self._save()               # what expired while the process was down goes now

    def _save(self):
        """Prune, then write the state atomically (temp file + rename), readable
        by the owner only. In memory (no path) it only prunes."""
        self._prune()
        if not self._path:
            return

        def dump(store):
            return {h: t.model_dump(mode="json", exclude={"token"}) for h, t in store.items()}

        state = {"version": _STATE_VERSION,
                 "clients": [c.model_dump(mode="json") for c in self._clients.values()],
                 "access": dump(self._access), "refresh": dump(self._refresh),
                 "pair": self._pair}
        folder = os.path.dirname(os.path.abspath(self._path))
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".oauth-state-")
        try:
            try:
                os.fchmod(fd, 0o600)
            except OSError as e:
                # Azure's /home is an SMB share, where chmod can be refused.
                # The file holds hashes, not usable tokens (only client secrets
                # as issued, docs/29), so carry on, but say so.
                if not getattr(self, "_chmod_warned", False):
                    log.warning("OAuth state %s: cannot restrict permissions (%s)",
                                self._path, e)
                    self._chmod_warned = True
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f)
            os.replace(tmp, self._path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
