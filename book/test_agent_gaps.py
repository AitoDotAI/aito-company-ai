"""Dogfooding gaps — the failure surfaces that motivate richer Aito v2 use
(vector/embedding search, and links + `_relate`/`_recommend`); see the proposal
`.ai/tasks/12-vector-and-graph.md`.

This is a **review-driven baseline**, not a passing feature: it asserts the
CURRENT (weak) behaviour so that when a capability lands, the diff is the proof
it worked — a French question that returns nothing today should later return the
right document; a multi-hop relationship that needs a hand-written join today
should later be one relational query. Requires a running Aito.
"""

import booktest as bt

from company_ai import deals, loaders, schema, search
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _seed(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)  # the company_id link target, loaded first
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)
    search.build_index(client)


def test_semantic_and_crosslingual_search_gap(t: bt.TestCaseRun) -> None:
    """GAP → vector/embedding search. Smart search ranks by Aito text-`$match`
    (tokenised, language-agnostic-by-accident). It has no notion of *meaning*, so
    a query that shares no tokens with the (English) documents fails, and a
    paraphrase that shares only common words returns everything. This pins the
    text-match floor of `search.search()`, which persists. The semantic layer
    LANDED (`search.ranked()` + an Azure embeddings deployment, `$nearest` over
    `search_vectors`, docs/23) closes it — proven in `book/test_search_vector.py`,
    where the same French query returns the right documents."""
    client = _client()
    _seed(client)

    def hits(query):
        return [h["title"] for h in search.search(client, query, kind="doc").derived["hits"]]

    cases = {
        "English, direct        ": "ideal customer profile",
        "French, same intent     ": "quels prospects contacter",   # 'which prospects to contact'
        "Paraphrase (retention)  ": "reducing churn and keeping customers",
        "Synonym (GTM)           ": "go-to-market plan",
    }
    t.h1("current text-match search over the (English) documents")
    results = {label: hits(q) for label, q in cases.items()}
    for label, q in cases.items():
        t.tln(f"  [{label}] '{q}'\n      -> {len(results[label])} hits: {results[label]}")

    t.h1("the gap, made concrete")
    french = results["French, same intent     "]
    para = results["Paraphrase (retention)  "]
    total_docs = len(client.query({"from": "documents", "limit": 1000})["hits"])
    t.tln(f"a clear French intent returns {len(french)} results (semantics lost in translation)")
    t.tln(f"a paraphrase returns {len(para)} of {total_docs} docs (token overlap on common words, no relevance)")
    # baseline assertions — a later vector capability should FLIP these:
    assert french == [], "baseline: the French query finds nothing via text-match"
    assert "Ideal customer profile" in results["English, direct        "], "English direct works"
    assert len(para) >= 4, "baseline: the paraphrase is noisy (low precision)"


def test_relational_graph_gap(t: bt.TestCaseRun) -> None:
    """GAP → links + `_relate`/`_recommend`, now CLOSED by the entity graph
    (Phase 1, `.ai/tasks/15`). A contact and a deal used to relate to a company
    only through a DENORMALISED `company` string, so a multi-hop question ("who
    should I reach at companies with a stalled deal?") had no single query — it
    was a hand-written join across three reads. Phase 1 added a `companies`
    entity and a `company_id` **link** on contacts/deals; the same question is
    now ONE relational pass — proven in
    `book/test_deals.py::test_who_to_reach_traverses_the_company_graph`. The
    `company` string stays as the denormalised display label, so the old
    hand-join below still runs and its answer matches the linked one — the diff
    is the proof the link landed."""
    client = _client()
    _seed(client)

    t.h1("the multi-hop that used to need a hand-written 3-read join")
    pipe = deals.pipeline(client).derived
    stalled = [d for d in pipe["deals"] if d.get("stalled")]
    stalled_companies = sorted({d["company"] for d in stalled})
    contacts = client.query({"from": "contacts", "limit": 100000})["hits"]
    reachable = [c for c in contacts if c["company"] in set(stalled_companies)]
    t.tln(f"stalled deals: {len(stalled)} at {len(stalled_companies)} companies")
    t.tln(f"contacts at those companies (hand-joined across 3 reads): {len(reachable)}")
    t.tln(f"  e.g. {[(c['name'], c['company']) for c in reachable[:3]]}")

    t.h1("now: the relationship is a link, so Aito traverses it in one query")
    t.tln(f"contacts.company    (display string): {schema.CONTACTS['columns']['company']}")
    t.tln(f"contacts.company_id (the entity link): {schema.CONTACTS['columns']['company_id']}")
    t.tln(f"deals.company_id    (the entity link): {schema.DEALS['columns']['company_id']}")
    graph = deals.who_to_reach(client, top_n=100).derived
    linked = sum(len(r["contacts"]) for r in graph["rows"])
    t.tln(f"who_to_reach() traverses company_id in one pass: "
          f"{graph['count']} stalled companies, {linked} contacts reached")
    t.tln("→ the same answer the hand-join produced, now a single relational query.")
    # the link landed; the denormalised string persists as the display label
    assert schema.CONTACTS["columns"]["company_id"]["link"] == "companies.company_id"
    assert schema.CONTACTS["columns"]["company"]["type"] == "String"
    assert linked == len(reachable), "the link traversal matches the hand-join exactly"
    assert len(reachable) > 0
