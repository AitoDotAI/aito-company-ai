"""Companies gate (Sales · Companies tab): contacts rolled up by company and
joined to their deals. Prints the roster as the dashboard table would show it,
then checks the invariants — every contact's company appears, open pipeline is
the sum of its open deals, and the sort is by open pipeline then size. Requires
a running Aito instance.
"""

import booktest as bt

from company_ai import companies, loaders, schema
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def test_roster_seed(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)

    result = companies.roster(client)
    rows = result.derived["companies"]

    t.h1("Companies — contacts + pipeline, most live money first (top 12)")
    t.tln(f"{'company':22} {'contacts':>8} {'segment':12} {'stage':12} "
          f"{'deals':>5} {'open':>4} {'pipeline_eur':>12} won")
    for c in rows[:12]:
        t.tln(f"{c['company']:22} {c['contacts']:>8} {(c['segment'] or '—'):12} "
              f"{c['stage']:12} {c['deals']:>5} {c['open_deals']:>4} "
              f"{c['pipeline_eur']:>12} {'yes' if c['won'] else ''}")
    t.tln(f"\ntotal companies: {result.derived['count']}")

    t.h1("Invariants")
    contacts = client.query({"from": "contacts", "limit": 100000})["hits"]
    deals = client.query({"from": "deals", "limit": 100000})["hits"]
    listed = {c["company"] for c in rows}
    contact_cos = {c["company"] for c in contacts}
    deal_cos = {d["company"] for d in deals}
    t.tln(f"every contact company listed: {contact_cos <= listed}")
    t.tln(f"every deal company listed: {deal_cos <= listed}")
    assert contact_cos <= listed and deal_cos <= listed

    # open pipeline of a company == sum of its open deals' value
    sample = next(c for c in rows if c["open_deals"] > 0)
    expected = sum(d["value_eur"] for d in deals
                   if d["company"] == sample["company"] and d["stage"] in schema.DEAL_OPEN_STAGES)
    t.tln(f"{sample['company']}: pipeline_eur={sample['pipeline_eur']} == "
          f"sum(open deals)={expected} → {sample['pipeline_eur'] == expected}")
    assert sample["pipeline_eur"] == expected

    # sort: open pipeline descending, then contact count descending
    keys = [(-c["pipeline_eur"], -c["contacts"], c["company"]) for c in rows]
    t.tln(f"sorted by (open pipeline, size, name): {keys == sorted(keys)}")
    assert keys == sorted(keys)


def test_roster_counts_contacts(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)

    t.h1("Contact counts match the rolodex, per company")
    contacts = client.query({"from": "contacts", "limit": 100000})["hits"]
    by_co: dict = {}
    for c in contacts:
        by_co[c["company"]] = by_co.get(c["company"], 0) + 1
    rows = {c["company"]: c for c in companies.roster(client).derived["companies"]}
    mismatches = [co for co, n in by_co.items() if rows[co]["contacts"] != n]
    t.tln(f"companies with contacts: {len(by_co)}")
    t.tln(f"contact-count mismatches: {mismatches}")
    assert not mismatches


def test_company_detail_is_the_graph_drill_in(t: bt.TestCaseRun) -> None:
    """Company drill-in (.ai/tasks/15): one company node opens to its people,
    deals, and notes — everything that links via `company_id`. This is what the
    Companies list drills into so a company shows its related notes."""
    client = _client()
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)

    d = companies.detail(client, "genco-oy").derived
    t.h1("the Genco Oy node — people, deals, notes via the company_id link")
    t.tln(f"name: {d['name']}")
    t.tln(f"people: {[c['name'] for c in d['contacts']]}")
    t.tln(f"deals:  {[dl['stage'] for dl in d['deals']]}")
    t.tln(f"notes:  {[n['title'] for n in d['documents']]}")
    assert d["name"] == "Genco Oy"
    assert any(c["name"] == "Carol Lane" for c in d["contacts"]), "its contact surfaces via the link"
    assert any("Genco" in n["title"] for n in d["documents"]), "its notes surface via the link"
