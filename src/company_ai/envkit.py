"""Env-isolated write tests.

Run a write sequence in a throwaway Aito *environment* branched from master
(copy-on-write, milliseconds) and drop it afterwards — so write tests don't
corrupt shared data and don't need a private instance per test. Envs are named
`test_<UTC timestamp>_<hash>` so serial/parallel runs never collide, and
`sweep_test_envs()` clears any left behind by a crashed run.

Needs a read-WRITE key on the target instance (envs are created/deleted). The
local container works as-is; a hosted instance needs a write key — the public
shared-demo key is read-only, so point AITO_* at a writable instance for these.

Also `md_table()` renders rows as a markdown table so a booktest snapshot shows
what a dashboard table widget renders, not just raw dicts.
"""

import os
from contextlib import contextmanager
from datetime import datetime, timezone

TAG = "test"


def env_name(tag: str = TAG) -> str:
    """A collision-proof throwaway env name (not snapshotted — it's random)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{tag}_{stamp}_{os.urandom(3).hex()}"


@contextmanager
def isolated_env(client, name: str | None = None):
    """Branch master into a fresh env, yield a client scoped to it, then drop
    it. Writes through the yielded client never touch master."""
    name = name or env_name()
    client.create_env(name)
    try:
        yield client.env_scoped(name)
    finally:
        try:
            client.delete_env(name)
        except Exception:
            pass


def sweep_test_envs(client, tag: str = TAG) -> list[str]:
    """Delete every `<tag>_*` env — the teardown that clears leftovers from a
    crashed run. Master and other envs are untouched."""
    dropped = []
    for env in client.list_envs():
        if not env.get("isMaster") and env["name"].startswith(tag + "_"):
            try:
                client.delete_env(env["name"])
                dropped.append(env["name"])
            except Exception:
                pass
    return sorted(dropped)


def md_table(rows: list[dict], columns: list) -> str:
    """Rows -> a markdown table. `columns` is a list of (header, key) pairs (or
    a bare key used as its own header). Mimics a dashboard table widget so the
    snapshot reads like the UI."""
    cols = [(c, c) if isinstance(c, str) else c for c in columns]
    lines = ["| " + " | ".join(h for h, _ in cols) + " |",
             "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(k, "")) for _, k in cols) + " |")
    return "\n".join(lines)
