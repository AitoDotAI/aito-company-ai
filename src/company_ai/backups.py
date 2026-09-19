"""Backups via Aito environments (docs/21).

An env is a copy-on-write branch of the whole database — a snapshot in
milliseconds using ~no extra disk (aito.ai/docs/api/envs). We keep two rolling
sets so a bad write (often the agent's) can be rolled back:

  - daily-<YYYY-MM-DD>  — the last 7 days
  - tx-<epoch>          — the last 16, for snapshotting before risky write-bursts

Restore *promotes* a snapshot into master — an atomic swap. Before that we
snapshot the current (about-to-be-replaced) state as prerestore-<epoch>, so a
restore is itself undoable. Rotation and restore-target selection are pure
functions (booktested); the env calls live on AitoClient. Loud on surprises
(rule 3): an unknown backup name or kind raises.
"""

from .aito import AitoClient

DAILY, TX, PRERESTORE = "daily", "tx", "prerestore"
KEEP = {DAILY: 7, TX: 16}
PREFIX = {DAILY: "daily-", TX: "tx-", PRERESTORE: "prerestore-"}


def snapshot_name(kind: str, stamp: str) -> str:
    assert kind in PREFIX, f"unknown backup kind {kind!r}"
    return f"{PREFIX[kind]}{stamp}"


def stale(names: list[str], kind: str, keep: int) -> list[str]:
    """Pure: the `kind` snapshots among `names` beyond the `keep` most recent.
    Our stamps (ISO date / zero-widening epoch) sort lexically = chronologically,
    so the newest keep sort highest; the rest are stale."""
    mine = sorted((n for n in names if n.startswith(PREFIX[kind])), reverse=True)
    return mine[keep:]


def list_backups(client: AitoClient) -> list[dict]:
    """Our snapshot envs (daily/tx/prerestore), newest first."""
    out = []
    for env in client.list_envs():
        for kind, pfx in PREFIX.items():
            if env["name"].startswith(pfx):
                out.append({"name": env["name"], "kind": kind})
                break
    out.sort(key=lambda x: x["name"], reverse=True)
    return out


def backup(client: AitoClient, kind: str, stamp: str, *, keep: int | None = None) -> dict:
    """Snapshot master as <kind>-<stamp>, then drop snapshots of that kind beyond
    the retention window. Re-running with the same stamp replaces that snapshot
    (idempotent for a given day)."""
    assert kind in KEEP, f"unknown backup kind {kind!r}; have {sorted(KEEP)}"
    name = snapshot_name(kind, stamp)
    existing = {e["name"] for e in client.list_envs()}
    if name in existing:                       # same-day re-run → refresh it
        client.delete_env(name)
    client.create_env(name)
    keep = KEEP[kind] if keep is None else keep
    after = [e["name"] for e in client.list_envs()]
    dropped = stale(after, kind, keep)
    for old in dropped:
        client.delete_env(old)
    return {"created": name, "kind": kind, "keep": keep, "dropped": dropped}


def restore(client: AitoClient, name: str, stamp: str, *, safety: bool = True) -> dict:
    """Promote a snapshot into master (the restore). First snapshot the current
    master as prerestore-<stamp> so the restore is undoable. Unknown name raises."""
    names = {e["name"] for e in client.list_envs()}
    assert name in names, f"unknown backup {name!r}; have {sorted(names)}"
    safety_name = None
    if safety:
        safety_name = snapshot_name(PRERESTORE, stamp)
        if safety_name not in names:
            client.create_env(safety_name)     # captures the current state first
    client.promote_env(name)
    return {"restored": name, "safety_snapshot": safety_name}
