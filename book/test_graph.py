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
        # the explanation is the point of the $why card: print each factor's
        # multiplicative lift so a change in the reasons shows up in the diff,
        # not just a change in the probability.
        for f in a.get("why", []):
            t.tln(f"    why: {f['label']:42} x{f['lift']:.2f}")
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
    # the explained card must come back with its reasons, and one of them must
    # be the fact that lives across the link — that is what distinguishes this
    # from a prediction any relational database could make.
    exp = next(a for a in board["answers"] if a["id"] == "explained-odds")
    assert exp.get("why"), "$why returned no lift factors"
    assert any(f["label"].startswith("company_id.") for f in exp["why"]), \
        f"no factor came from across the link; got {[f['label'] for f in exp['why']]}"
    assert exp["p"] > board["baseline_p"], \
        "a deal with a champion, no blocker and a good industry must beat the base rate"


class _Ranked:
    """A stand-in engine that ranks field values the way Aito's predict would,
    so the question resolvers can be read without loading a second dataset."""

    def __init__(self, deals_by_segment, roles_by_industry):
        self.deals = deals_by_segment
        self.roles = roles_by_industry

    def predict(self, request):
        if request["from"] == "deals" and request["predict"] == "segment":
            values = self.deals
        elif request["from"] == "contacts" and request["predict"] == "role":
            values = self.roles.get(request["where"]["company_id.industry"], [])
        else:
            values = []
        return {"hits": [{"$value": v, "$p": 1 / (i + 2)} for i, v in enumerate(values)]}


def test_questions_follow_the_loaded_data(t: bt.TestCaseRun) -> None:
    """The cards used to name accounting, CFO and CTO outright — this repo's
    home turf — so on another company's data the showcase came back empty."""
    from company_ai import schema

    t.h1("a consultancy whose work is mostly public sector")
    engine = _Ranked(["public-sector", "retail", "industry"],
                     {"public-sector": ["CTO", "Head of IT", "IT Manager", "Procurement Lead"]})
    before = schema.TECHNICAL_ROLES
    schema.TECHNICAL_ROLES = {"CTO", "Head of IT"}       # their vocabulary file
    try:
        for qid, prose, request in graph.questions(engine):
            t.tln(f"{qid:20} {prose}")
        t.h2("the technical condition, as sent")
        cto = dict((q[0], q[2]) for q in graph.questions(engine))["cto-odds"]
        t.tln(str(cto["where"]))
    finally:
        schema.TECHNICAL_ROLES = before

    t.h1("an empty instance falls back to the configured vocabulary, not to ours")
    before_segments = schema.SEGMENTS
    schema.SEGMENTS = {"public-sector", "retail", "other"}   # their vocabulary file
    try:
        for qid, prose, _ in graph.questions(_Ranked([], {}))[:3]:
            t.tln(f"{qid:20} {prose}")
    finally:
        schema.SEGMENTS = before_segments


def test_a_multi_role_condition_runs_on_a_real_engine(t: bt.TestCaseRun) -> None:
    """`{"role": {"$or": [...]}}` inside `$exists` is the shape a deployment with
    more than one technical title produces. Checked against the engine, not
    assumed."""
    from company_ai import schema

    client = _client()
    _seed(client)
    before = schema.TECHNICAL_ROLES
    schema.TECHNICAL_ROLES = {"CTO", "IT Manager"}
    try:
        board = graph.board(client)
    finally:
        schema.TECHNICAL_ROLES = before
    cto = next(a for a in board["answers"] if a["id"] == "cto-odds")
    t.tln(f"question: {cto['question']}")
    t.tln(f"failed queries: {board['failed'] or 'none'}")
    t.tln(f"technical-contact card answered: {'error' not in cto and bool(cto.get('hits'))}")
    t.tln(f"the view's label: {board['technical_role']!r}")
