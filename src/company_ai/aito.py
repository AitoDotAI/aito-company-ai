"""Thin HTTP client for one Aito instance.

Transport and loud errors only; every piece of predictive logic is the
query body passed through, never anything computed here.
"""

from typing import Any
from urllib.parse import urlparse

import requests


class AitoError(RuntimeError):
    pass


class AitoClient:
    def __init__(self, base_url: str, api_key: str = "", timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method: str, path: str, body: Any = None,
                 base: str | None = None) -> Any:
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        response = requests.request(
            method, f"{base or self.base_url}{path}", json=body, headers=headers,
            timeout=self.timeout
        )
        if response.status_code >= 400:
            raise AitoError(f"{method} {path} -> {response.status_code}: {response.text}")
        return response.json()

    def version(self) -> dict:
        """Build info for the instance (read-only, best effort). `/version` is
        served at the host root, not under the db path — try the db-scoped URL
        first, then fall back to the host root. Returns {"reachable": False} if
        neither answers rather than raising; a diagnosis should report an
        unreachable instance, not crash on it."""
        root = f"{urlparse(self.base_url).scheme}://{urlparse(self.base_url).netloc}"
        headers = {"x-api-key": self.api_key} if self.api_key else {}
        for url in (f"{self.base_url}/version", f"{root}/version"):
            try:
                response = requests.get(url, headers=headers, timeout=self.timeout)
            except requests.RequestException:
                continue
            if response.ok:
                return {"reachable": True, **response.json()}
        return {"reachable": False}

    # schema
    def get_schema(self) -> dict:
        return self._request("GET", "/api/v2/schema")

    _ensured: set = set()   # tables known to exist this process (class-wide cache)

    def create_table(self, name: str, definition: dict) -> Any:
        # v2 engine tables are "collection"s (predict/recommend/_modify need it);
        # our schema dicts are written as v1 "table" — swap on the way out.
        return self._request("PUT", f"/api/v2/schema/{name}",
                             {**definition, "type": "collection"})

    def create_view(self, name: str, definition: dict) -> Any:
        """Create a v2 view (union / join) — a materialised, read-only, queryable
        collection over other tables. Passed through as-is (a view is not a
        collection). Refresh it with `refresh_view` after the sources change."""
        return self._request("PUT", f"/api/v2/schema/{name}", definition)

    def refresh_view(self, name: str) -> Any:
        """Re-materialise a view from its sources (v2 `_refresh`); idempotent."""
        return self._request("POST", f"/api/v2/schema/{name}/_refresh")

    def ensure_table(self, name: str, definition: dict) -> None:
        """Create the table if it's absent (idempotent, cached per process). App-
        state tables (chats) must materialise on an
        instance that predates them, without a separate migration step."""
        if name in AitoClient._ensured:
            return
        try:
            present = name in self.get_schema()["schema"]
        except AitoError:
            present = False
        if not present:
            self.create_table(name, definition)
        AitoClient._ensured.add(name)

    def delete_table(self, name: str) -> Any:
        """Drop a table and its data. Missing table is fine: drop is for reload."""
        if name not in self.get_schema()["schema"]:
            return {"status": "absent"}
        return self._request("DELETE", f"/api/v2/schema/{name}")

    def add_column(self, table: str, column: str, definition: dict) -> Any:
        """Add a column to an existing table without dropping it. Existing
        rows read null for the new column until they are (re)loaded."""
        return self._request("PUT", f"/api/v2/schema/{table}/{column}", definition)

    def delete_column(self, table: str, column: str) -> Any:
        """Drop a column. v2 has no DELETE on the column endpoint (405); it uses
        declarative `_apply` — re-declare the schema without the column. The drop
        is lossy, so it needs `?confirm=true`.

        `_apply` is NOT idempotent for `link` columns: re-declaring an unchanged
        link on a POPULATED table is rejected as an incompatible type change
        (`column '…' (String -> String is a lossy or incompatible type change)`),
        an Aito limitation (.ai/tasks/05 note 9). So when the table carries a link
        and the declarative drop is refused, fall back to a row-preserving reload:
        read the rows, drop + recreate the table from the desired schema (a fresh
        empty table takes the link cleanly), and re-upload. The row count is
        preserved either way; the caller sees the column gone."""
        current = self._request("GET", f"/api/v2/schema/{table}")
        desired = {"type": current.get("type", "collection"),
                   "columns": {k: v for k, v in current["columns"].items() if k != column}}
        try:
            return self._request("POST", f"/api/v2/schema/{table}/_apply?confirm=true", desired)
        except AitoError:
            # _apply refused — only the link-idempotency case is recoverable; a
            # table without links re-raises (the failure is something else).
            if not any("link" in spec for spec in desired["columns"].values()):
                raise
            rows = self.query({"from": table, "limit": 1_000_000})["hits"]
            kept = [{k: r[k] for k in desired["columns"] if k in r} for r in rows]
            self._request("DELETE", f"/api/v2/schema/{table}")
            self.create_table(table, desired)
            if kept:
                self.upload_batch(table, kept)
            return {"reloaded_to_drop_link_table_column": True, "rows": len(kept)}

    # environments — copy-on-write snapshots of the whole database (docs/21,
    # aito.ai/docs/api/envs). A branch of master is a millisecond, ~zero-disk
    # snapshot; promoting one is an atomic swap into master (the restore). Used
    # by backups.py; the admin `_envs` endpoints need a read-write key.
    def _db_root(self) -> str:
        """The database-level URL. env-management (`_envs`) lives at the database
        level, not inside an env (aito-core v2.3.x — the env-scoped path now
        404s). base_url may point at a specific env (…/db/<db>/env/<name>); strip
        that suffix for these admin calls."""
        i = self.base_url.find("/env/")
        return self.base_url[:i] if i != -1 else self.base_url

    def list_envs(self) -> list[dict]:
        """[{isMaster, name}, …] — master plus every snapshot."""
        return self._request("GET", "/api/v2/_envs", base=self._db_root())["envs"]

    def create_env(self, name: str, source: str | None = None) -> Any:
        """Branch a new env (default from master) — a snapshot."""
        return self._request("POST", "/api/v2/_envs",
                             {"name": name, "basedOn": source or "env.master"},
                             base=self._db_root())

    def delete_env(self, name: str) -> Any:
        return self._request("DELETE", f"/api/v2/_envs/{name}", base=self._db_root())

    def promote_env(self, name: str) -> Any:
        """Atomically swap this env's state into master — the restore."""
        return self._request("POST", f"/api/v2/_envs/{name}/promote", base=self._db_root())

    def env_scoped(self, name: str) -> "AitoClient":
        """A client that targets a named env (URL /db/<db>/env/{name}/…) — e.g.
        to read a snapshot's row counts before restoring it. Envs are database-
        level siblings, so scope from the db root (never nest under an already
        env-scoped base — v2.3.x rejects /env/<a>/env/<b>)."""
        return AitoClient(f"{self._db_root()}/env/{name}", self.api_key, self.timeout)

    # data
    def upload_batch(self, table: str, rows: list[dict]) -> Any:
        return self._request("POST", f"/api/v2/data/{table}/batch", rows)

    def delete_entries(self, table: str, where: dict) -> Any:
        """Delete the entries matching a Search-like `where` (not a whole-table
        drop). Used for per-row updates of the app-state tables (chats) so they
        don't need a full-table rewrite. In v2 this is a
        `_modify` delete op: the predicate rides in the `delete` field."""
        return self._request("POST", "/api/v2/data/_modify",
                             {"from": table, "delete": where})

    def update_entries(self, table: str, where: dict, set_fields: dict) -> Any:
        """Update in place the rows matching `where` (v2 `_modify` update), then
        `optimize` to flush — so a caller that re-reads sees its own change.

        The flush is built in ON PURPOSE: on this build a bare `_modify` update
        is applied but stays INVISIBLE to reads until the next write (see
        `optimize`), a silent data-integrity trap. Making the flush part of the
        primitive means a future caller cannot reintroduce the bug by forgetting
        it — the only correct `_modify` update is a flushed one. Callers that need
        to *prove* the write landed should still read back and assert (rule 3);
        see `log.claim_todo`."""
        result = self._request("POST", "/api/v2/data/_modify",
                               {"update": table, "where": where, "set": set_fields})
        self.optimize(table)   # flush: the update is invisible to reads until the next write
        return result

    def optimize(self, table: str) -> Any:
        """Compact a collection. Needed as a *flush* after a `_modify` update:
        on this build the update is applied but stays INVISIBLE to reads until
        the next write to the collection (docs/24 bug 5, re-probed 2026-08-15 —
        still reproduces). An optimize is that next write, so a caller that
        updates then re-reads sees its own change instead of the stale row.
        Takes an empty body; a bodyless POST is a 400."""
        return self._request("POST", f"/api/v2/data/{table}/optimize", {})

    def count(self, table: str) -> int:
        return self.query({"from": table, "limit": 0})["total"]

    # inference endpoints: bodies are composed by callers, per CLAUDE.md rule 2
    def query(self, body: dict) -> Any:
        return self._request("POST", "/api/v2/_query", body)

    def predict(self, body: dict) -> Any:
        return self._request("POST", "/api/v2/_predict", body)

    def recommend(self, body: dict) -> Any:
        return self._request("POST", "/api/v2/_recommend", body)

    def relate(self, body: dict) -> Any:
        return self._request("POST", "/api/v2/_relate", body)

    def similarity(self, body: dict) -> Any:
        return self._request("POST", "/api/v2/_similarity", body)

    def match(self, body: dict) -> Any:
        return self._request("POST", "/api/v2/_match", body)
