"""The account's facts where a call is prepared (td-20261118105636099520):
the technical attribute slots the CRO asked for, and the active facts in
opener_context(contact) and company_detail(company), grouped as briefing
groups them. The trigger: four questions drafted to a prospect whose answers
were already in old notes. Requires a running Aito instance."""

import booktest as bt

from company_ai import companies, facts, graph, loaders, log, queries, schema
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

SEED = loaders._read_csv(SEED_DIR / "facts.csv")
ACCOUNT = SEED[0]["company"]
AID = loaders.company_slug(ACCOUNT)
CONTACT = SEED[0]["stakeholder_id"]
HELD = next(f for f in SEED if f["kind"] == "hold")["company"]
TECHNICAL = {"volume": "About 10 million rows a year in the spec queue",
             "data_model": "Invoices and rows in one wide table",
             "load": "Nightly batch, one peak at month end",
             "infra": "Azure, their own subscription",
             "stack": "Python services over Postgres"}


def _seeded() -> AitoClient:
    config = Config.from_env()
    client = AitoClient(config.instance_url, config.api_key)
    loaders.create_schema(client)
    loaders.load_all(client, SEED_DIR)
    return client


def _active(company: str) -> set[str]:
    return {f["fact_id"] for f in SEED if f["company"] == company and not f["superseded_by"]}


def _ids(groups: dict) -> set[str]:
    """Every fact id in a briefing-shaped facts group."""
    out: set[str] = {r["source"]["id"] for r in groups["hold"]["facts"]}
    for rows in (*groups["roles"].values(), *groups["attributes"].values(), groups["decisions"],
                 groups["open_questions"], groups["commitments"], *groups["contact_info"].values()):
        out |= {r["source"]["id"] for r in rows}
    return out


def test_technical_attribute_slots_are_accepted(t: bt.TestCaseRun) -> None:
    client = _seeded()
    note = sorted(h["doc_id"] for h in client.query(
        {"from": "documents", "where": {"company_id": AID}, "select": ["doc_id"], "limit": 100})["hits"])[0]
    t.h1("add_fact(kind=attribute) in each new slot")
    written = {}
    for slot, statement in TECHNICAL.items():
        row = log.add_fact(client, company=ACCOUNT, kind="attribute", slot=slot, statement=statement,
                           source_kind="doc", source_id=note, valid_from="2026-11-18", author="cro")
        written[slot] = row["fact_id"]
        t.tln(f"  {slot}: {statement!r} -> warnings {row['warnings']}")
        assert row["warnings"] == []
    t.h1("briefing lists them under attributes, by slot")
    b = companies.briefing(client, ACCOUNT).derived["facts"]
    t.tln(f"  slot order: {list(b['attributes'])}")
    for slot, fact_id in written.items():
        # newest first in its slot, after it the seed's own facts there
        seeded = [f["fact_id"] for f in SEED if f["kind"] == "attribute" and f["slot"] == slot]
        assert [r["source"]["id"] for r in b["attributes"][slot]] == [fact_id, *seeded], slot
    t.h1("Nothing was renamed")
    old = {"budget_cycle", "procurement", "billing_model", "tooling", "headcount", "deployment",
           "pain", "other"}
    t.tln(f"  attribute slots: {sorted(schema.FACT_SLOTS['attribute'])}")
    assert old | set(TECHNICAL) == schema.FACT_SLOTS["attribute"]
    assert set(facts.ATTRIBUTE_ORDER) == schema.FACT_SLOTS["attribute"]


def test_opener_context_carries_the_account_facts(t: bt.TestCaseRun) -> None:
    client = _seeded()
    out = queries.opener_context(client, CONTACT).derived
    t.h1(f"opener_context({CONTACT}), a contact at the seed account")
    t.tln(f"  keys: {sorted(out)}")
    t.tln(f"  evidence rows: {len(out['evidence'])}")
    acct = out["account"]
    t.tln(f"  account: {acct['company_id']}, hold {acct['facts']['hold']['status']}")
    for slot, rows in acct["facts"]["attributes"].items():
        if rows:
            t.tln(f"    attribute/{slot}: {[r['statement'] for r in rows]}")
    assert acct["company_id"] == AID
    assert _ids(acct["facts"]) == _active(ACCOUNT), "every active fact, and only those"
    assert out["evidence"] == queries.opener_context(client, CONTACT).derived["evidence"]

    t.h1("A contact at a held account sees the hold first")
    held = client.query({"from": "contacts", "where": {"company_id": loaders.company_slug(HELD)},
                         "select": ["contact_id"], "limit": 1})["hits"][0]["contact_id"]
    hold = queries.opener_context(client, held).derived["account"]["facts"]["hold"]["status"]
    t.tln(f"  {held}: hold {hold}")
    assert hold == "HOLD"


def test_company_detail_carries_the_account_facts(t: bt.TestCaseRun) -> None:
    client = _seeded()
    d = companies.detail(client, AID).derived
    t.h1(f"company_detail({AID})")
    t.tln(f"  keys: {sorted(d)}")
    t.tln(f"  account_facts: {len(_ids(d['account_facts']))} active, hold {d['account_facts']['hold']['status']}")
    assert _ids(d["account_facts"]) == _active(ACCOUNT)
    briefed = companies.briefing(client, AID).derived["facts"]
    assert d["account_facts"] == briefed, "grouped exactly as briefing groups them"
    t.h1("The node's harvested facts stay under `facts`, unchanged")
    t.tln(f"  facts keys: {sorted(d['facts'] or {})}")
    assert set(d["facts"]) == set(graph.COMPANY_FACTS)
