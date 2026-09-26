"""Knowledge-graph gate (docs/31): the company node carries harvested facts,
and Aito walks the company_id link in both directions.

The point of the snapshot is the REQUEST next to the RESPONSE — link traversal
is a young corner of Aito, so the query that produced a number is the review
artifact. Requires a running Aito instance.
"""

import booktest as bt

from company_ai import graph, loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _seed(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)


def test_company_facts_are_harvested(t: bt.TestCaseRun) -> None:
    t.h1("The company node carries facts derived from its contacts and deals")
    rows = loaders.companies_from_csvs(SEED_DIR)
    t.tln(f"  companies: {len(rows)}")
    by_rel: dict[str, int] = {}
    for r in rows:
        by_rel[r["relationship"]] = by_rel.get(r["relationship"], 0) + 1
    t.tln(f"  relationship: {dict(sorted(by_rel.items()))}")
    t.tln(f"  total MRR: {sum(r['mrr_eur'] for r in rows)}")
    t.h2("A customer, a prospect and an untouched account")
    for rel in ("customer", "prospect", "none"):
        row = next(r for r in rows if r["relationship"] == rel)
        t.tln(f"  {rel:9} {row['name']:16} industry={row['industry']:11} "
              f"mrr={row['mrr_eur']:6} open_deals={row['open_deals']} "
              f"contacts={row['contact_count']}")
    # the harvest must agree with the rows it summarises (rule 3)
    customers = [r for r in rows if r["relationship"] == "customer"]
    assert all(r["mrr_eur"] > 0 for r in customers), \
        "a customer with no MRR means the won-deal harvest disagrees with deals.csv"
    assert all(r["relationship"] != "none" or r["open_deals"] == 0 for r in rows), \
        "an account with no relationship cannot have an open deal"


def test_graph_questions(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed(client)
    t.h1("Each question is one Aito query — request, then what came back")
    board = graph.board(client)
    t.tln(f"  {board['ok']}/{len(board['answers'])} queries answered; "
          f"failed: {board['failed'] or 'none'}")
    for a in board["answers"]:
        t.h2(a["question"])
        t.tln(f"  request:  {a['request']}")
        if "error" in a:
            t.tln(f"  ERROR:    {a['error']}")
            continue
        t.tln(f"  total:    {a['total']}")
        for hit in a["hits"][:3]:
            t.tln(f"    {dict(sorted(hit.items()))}")
    # Traversal must actually traverse: a silently-unresolved dotted field
    # returns zero rows rather than raising (docs/31, sharp edges), so an
    # all-empty board would look identical to a broken link.
    assert not board["failed"], f"graph queries failed: {board['failed']}"
    people = next(a for a in board["answers"] if a["id"] == "people-at-customers")
    assert people["total"] > 0, \
        "forward traversal company_id.relationship returned nothing — link unresolved?"
    refs = next(a for a in board["answers"] if a["id"] == "accounts-with-cto")
    assert refs["total"] > 0, \
        "reverse traversal $refs.contacts.company_id returned nothing — link unresolved?"
