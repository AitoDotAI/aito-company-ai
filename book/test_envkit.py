"""The env-isolation pattern (company_ai/envkit.py) in action: run a write sequence
in a throwaway Aito env, render the result as the dashboard table would, and
prove master is untouched — then a teardown that sweeps leftover test envs.

Runs against whatever AITO_* points at, provided it has a read-WRITE key (env
create/delete). The local container works as-is.
"""

import os
from datetime import date

import booktest as bt
from company_ai import envkit

from company_ai import loaders, log, todos
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

AS_OF = date(2026, 6, 17)


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _env_tests_ok(t: bt.TestCaseRun) -> bool:
    """Env-management tests create / promote / DROP envs at the DATABASE level —
    safe ONLY on a disposable, single-tenant instance (a local container). On a
    shared multi-env instance they sweep sibling envs (they once wiped the demo
    db's booktest/v2/v2suite). So they are opt-in and never run against shared."""
    url = Config.from_env().instance_url
    if os.environ.get("COMPANY_AI_ENV_TESTS") == "1" and "shared.aito.ai" not in url:
        return True
    t.tln("SKIPPED — env-management test. It creates/drops envs at the db level,")
    t.tln("which is destructive on a shared multi-env instance. To run it, set")
    t.tln("COMPANY_AI_ENV_TESTS=1 against a disposable single-tenant instance")
    t.tln("(e.g. a local Aito container), never the shared demo.")
    return False


def _seed_master(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_todos(client, SEED_DIR)


def test_write_sequence_isolated_in_an_env(t: bt.TestCaseRun) -> None:
    if not _env_tests_ok(t):
        return
    client = _client()
    _seed_master(client)
    master_ops = len(todos.pipeline(client, "operations", as_of=AS_OF).derived["todos"])

    with envkit.isolated_env(client) as env:
        t.h1("write a todo — but only inside the throwaway env")
        log.add_todo(env, area="operations", title="Renew TLS cert", priority=1,
                     detail="letsencrypt renewal")
        rows = todos.pipeline(env, "operations", as_of=AS_OF).derived["todos"]
        added = next(r for r in rows if r["title"] == "Renew TLS cert")
        t.tln(f"operations todos: master={master_ops}, env={len(rows)} (env = master + 1)")

        t.h1("the Operations pipeline in this env — rendered as the dashboard table")
        t.tln(envkit.md_table([added], [("#", "priority"), ("Action", "title"),
                                        ("Area", "area"), ("Status", "status")]))

    t.h1("the env is dropped; master never saw the write")
    after = todos.pipeline(client, "operations", as_of=AS_OF).derived["todos"]
    t.tln(f"master operations todos still {len(after)}; "
          f"'Renew TLS cert' on master = {any(r['title'] == 'Renew TLS cert' for r in after)}")
    assert len(after) == master_ops


def test_sweep_clears_leftover_test_envs(t: bt.TestCaseRun) -> None:
    if not _env_tests_ok(t):
        return
    client = _client()
    # simulate two envs left behind by crashed runs (no cleanup)
    a, b = envkit.env_name(), envkit.env_name()
    client.create_env(a)
    client.create_env(b)
    present = {e["name"] for e in client.list_envs()}
    t.h1("sweep_test_envs() is the teardown for anything a crash left behind")
    t.tln(f"two leftover test envs present: {a in present and b in present}")
    envkit.sweep_test_envs(client)
    remaining = {e["name"] for e in client.list_envs()}
    t.tln(f"after sweep — any test_ env remaining: {any(n.startswith('test_') for n in remaining)}")
    assert a not in remaining and b not in remaining
