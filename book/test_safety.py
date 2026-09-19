"""Safety gate: local-instance detection and the clear command.

Covers the P0 finding (synthetic seed silently written to the wrong db):
the host check that backs the seed guard, and the clear/truncate command.
The is_local check is pure; clear needs a running Aito instance.
"""

import booktest as bt

from company_ai import loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config, instance_host, is_local_instance


def test_local_instance_detection(t: bt.TestCaseRun) -> None:
    t.h1("is_local_instance / instance_host")
    cases = [
        "http://localhost:9005",
        "http://127.0.0.1:8770",
        "http://0.0.0.0:2000",
        "https://aito.example.com/db/aito",
        "https://aito-demo.example.com/db/demo",
    ]
    for url in cases:
        t.tln(f"  local={is_local_instance(url)!s:5} host={instance_host(url)}")
    # the guard rule, stated as a truth table
    t.h2("seed guard: --seed blocked unless local or --force")
    for url in ("http://localhost:9005", "https://aito.example.com/db/aito"):
        for force in (False, True):
            blocked = (not is_local_instance(url)) and not force
            t.tln(f"  seed url={instance_host(url):28} force={force!s:5} -> "
                  f"{'BLOCKED' if blocked else 'allowed'}")


def test_clear_table(t: bt.TestCaseRun) -> None:
    config = Config.from_env()
    client = AitoClient(config.instance_url, config.api_key)
    loaders.create_schema(client)
    loaders.load_deals(client, SEED_DIR)
    t.h1("clear empties the table but keeps the schema")
    t.tln(f"deals before clear: {client.count('deals')}")
    loaders.clear_table(client, "deals")
    t.tln(f"deals after clear:  {client.count('deals')}")
    present = "deals" in client.get_schema()["schema"]
    t.tln(f"deals table still present (schema intact): {present}")
    assert client.count("deals") == 0 and present


def test_clear_unknown_table_asserts(t: bt.TestCaseRun) -> None:
    t.h1("Clearing an unknown table raises")
    config = Config.from_env()
    client = AitoClient(config.instance_url, config.api_key)
    try:
        loaders.clear_table(client, "invoices")
        raise RuntimeError("cleared an unknown table")
    except AssertionError as e:
        t.tln(str(e))
