"""Backups via Aito environments (docs/21). The rotation/target selection is a
pure function (deterministic). The end-to-end test exercises the real env API
on the local instance: snapshot master, break it, promote the snapshot back,
and confirm the data returns — then clean up every env it made."""

import os

import booktest as bt

from company_ai import backups, loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _env_tests_ok(t: bt.TestCaseRun) -> bool:
    """Backup/restore create / promote / DROP envs at the DATABASE level — safe
    ONLY on a disposable, single-tenant instance. On a shared multi-env instance
    they sweep sibling envs. Opt-in; never run against shared (see test_envkit)."""
    url = Config.from_env().instance_url
    if os.environ.get("COMPANY_AI_ENV_TESTS") == "1" and "shared.aito.ai" not in url:
        return True
    t.tln("SKIPPED — env-management test (create/drop envs at the db level). Set")
    t.tln("COMPANY_AI_ENV_TESTS=1 against a disposable single-tenant instance,")
    t.tln("never the shared demo.")
    return False


def test_stale_selects_old_snapshots(t: bt.TestCaseRun) -> None:
    t.h1("rotation: keep the N most recent of a kind, drop the rest (pure)")
    names = [
        "env.master", "daily-2026-06-10", "daily-2026-06-11", "daily-2026-06-12",
        "tx-1000", "tx-1002", "tx-1001", "prerestore-9",
    ]
    t.tln(f"daily, keep 2 -> drop {backups.stale(names, backups.DAILY, 2)}")
    t.tln(f"tx, keep 2    -> drop {backups.stale(names, backups.TX, 2)}")
    t.tln(f"daily, keep 7 -> drop {backups.stale(names, backups.DAILY, 7)}")
    # newest sort highest; the oldest are dropped; other kinds untouched
    assert backups.stale(names, backups.DAILY, 2) == ["daily-2026-06-10"]
    assert backups.stale(names, backups.TX, 2) == ["tx-1000"]
    assert backups.stale(names, backups.DAILY, 7) == []


def test_backup_and_restore_roundtrip(t: bt.TestCaseRun) -> None:
    if not _env_tests_ok(t):
        return
    client = _client()
    loaders.create_schema(client)
    loaders.load_materials(client, SEED_DIR)
    try:
        n0 = client.count("materials")
        t.h1("snapshot master")
        made = backups.backup(client, "daily", "2026-06-17")
        t.tln(f"created {made['created']}; snapshots now: "
              f"{[e['name'] for e in client.list_envs() if not e['isMaster']]}")

        t.h1("the agent breaks things: drop the materials table")
        client.delete_table("materials")
        gone = "materials" not in client.get_schema()["schema"]
        t.tln(f"materials table present after break: {not gone}")

        t.h1("restore: promote the snapshot back into master")
        res = backups.restore(client, "daily-2026-06-17", "restorestamp")
        n1 = client.count("materials")
        t.tln(f"restored from {res['restored']} (undo point: {res['safety_snapshot']})")
        t.tln(f"materials rows: before={n0}, after restore={n1}")
        assert n1 == n0

        t.h1("rotation drops snapshots beyond the keep window")
        for stamp in ("2026-06-20", "2026-06-21"):
            backups.backup(client, "daily", stamp, keep=1)
        kept = sorted(e["name"] for e in client.list_envs() if e["name"].startswith("daily-"))
        t.tln(f"daily snapshots after keep=1: {kept}")
        assert kept == ["daily-2026-06-21"]
    finally:
        for env in client.list_envs():
            if not env["isMaster"]:
                client.delete_env(env["name"])
