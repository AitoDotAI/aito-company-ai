"""Smart-search gate (docs/23): build the index by fanning out over the
sources, then rank items by Aito text-`_match`. The numerical check (rule 4):
a distinctive query ranks its item first, above an unrelated one. Prints the
Aito request/response and the ranked hits (rule 5). Requires a running Aito
instance.
"""

import booktest as bt

from company_ai import loaders, log, search
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _seed_index(client: AitoClient):
    """Seed a deterministic index: the contacts/deals sources plus a small,
    fixed pair of documents (reset first, since the store is a shared collection
    now). Returns (stats, {name: doc_id})."""
    loaders.create_schema(client)
    loaders.clear_table(client, "documents")   # only our two docs, for determinism
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    ids = {
        "pricing": log.add_document(
            client, title="Pricing playbook", kind="internal", area="sales",
            body="How we price pilots and negotiate annual contracts with procurement.",
        )["doc_id"],
        "onboarding": log.add_document(
            client, title="Onboarding guide", kind="docs", area="operations",
            body="Steps to onboard a new customer: kickoff, data import, training.",
        )["doc_id"],
    }
    return search.build_index(client), ids


def test_build_index(t: bt.TestCaseRun) -> None:
    client = _client()
    stats, _ = _seed_index(client)
    t.h1("Index built by fanning out over documents + contacts + deals")
    t.tln(f"indexed: {stats['indexed']}")
    for kind in sorted(stats["by_kind"]):
        t.tln(f"  {kind:8} {stats['by_kind'][kind]}")


def test_search_ranks_by_match(t: bt.TestCaseRun) -> None:
    client = _client()
    _, ids = _seed_index(client)

    t.h1("Search 'pricing pilots procurement' — the pricing doc should lead")
    res = search.search(client, "pricing pilots procurement", top_n=5)
    for i, h in enumerate(res.derived["hits"], 1):
        t.tln(f"  {i}. [{h['kind']:7}] {h['title']}")

    hits = res.derived["hits"]
    assert hits, "a text query must return ranked hits"
    t.tln(f"\ntop hit: [{hits[0]['kind']}] {hits[0]['title']}")

    # rule 4 (numerical): the distinctive doc outranks the unrelated onboarding
    # doc. Asserted over the DOC kind rather than the mixed top-5: "pilot" is
    # also a deal stage, so the size of the seed's open pipeline decides how
    # many deals crowd the first five rows — which has nothing to do with the
    # claim being made here, and silently turned this into 99 < 99 when the
    # seed grew.
    docs = search.search(client, "pricing pilots procurement", kind="doc", top_n=5)
    t.h2("Same query, documents only")
    for i, h in enumerate(docs.derived["hits"], 1):
        t.tln(f"  {i}. {h['title']}")
    ranks = {h["item_id"]: i for i, h in enumerate(docs.derived["hits"])}
    assert ranks.get(f"doc:{ids['pricing']}", 99) < ranks.get(f"doc:{ids['onboarding']}", 99), \
        "the pricing doc must outrank the onboarding doc for a pricing query"
    t.tln("pricing doc outranks onboarding doc: True")


def test_filter_by_kind(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed_index(client)

    t.h1("kind='deal' restricts results to deals")
    res = search.search(client, "accounting", kind="deal", top_n=5)
    t.tln(f"count: {res.derived['count']}; all deals: "
          f"{all(h['kind'] == 'deal' for h in res.derived['hits'])}")
    for h in res.derived["hits"][:5]:
        t.tln(f"  {h['title']}")
    assert all(h["kind"] == "deal" for h in res.derived["hits"])


def test_empty_query_and_bad_kind_raise(t: bt.TestCaseRun) -> None:
    client = _client()
    t.h1("An empty query or unknown kind raises (rule 3)")
    for label, call in {
        "empty query": lambda: search.search(client, "   "),
        "unknown kind": lambda: search.search(client, "x", kind="invoice"),
    }.items():
        try:
            call()
            raise RuntimeError(f"{label}: was accepted")
        except AssertionError as e:
            t.tln(f"{label}: {e}")


def test_accented_query_is_not_shredded(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed_index(client)
    # a document carrying an accented Finnish term; add_document refreshes the view
    doc_id = log.add_document(
        client, title="Hinnoittelun päätös", kind="internal", area="sales",
        body="Asiakkaan päätös hinnoittelusta ja pilotista.")["doc_id"]

    t.h1("Accented terms survive tokenization (not shredded into single chars)")
    # the fix, proven deterministically: ä/ö keep the word whole
    clause = search._match_clause("Hämeenlinnan päätös")
    terms = [next(iter(o["content"].values())) for o in clause["$or"]]
    t.tln(f"tokens('Hämeenlinnan päätös') = {terms}")
    assert terms == ["hämeenlinnan", "päätös"], terms

    t.h1("…and the accented query retrieves the accented document")
    res = search.search(client, "päätös", top_n=5)
    for i, h in enumerate(res.derived["hits"], 1):
        t.tln(f"  {i}. [{h['kind']:7}] {h['title']}")
    ids = {h["item_id"] for h in res.derived["hits"]}
    assert f"doc:{doc_id}" in ids, f"accented doc not found; got {ids}"


def test_symbol_only_query_returns_empty_not_500(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed_index(client)
    t.h1("A query with no searchable terms returns empty — never a 500 (rule 3 is about data)")
    res = search.search(client, "??? !!! ---", top_n=5)
    t.tln(f"count: {res.derived['count']}; hits: {res.derived['hits']}")
    assert res.derived["count"] == 0 and res.derived["hits"] == []


def test_quick_find_across_entities(t: bt.TestCaseRun) -> None:
    """The top-bar quick-find (docs/25): a literal jump-to across companies,
    notes, todos, and contacts, each with a deep-link `target`. A lookup — the
    ranked smart search stays the Search view's job (rule 2)."""
    client = _client()
    loaders.create_schema(client)
    loaders.clear_table(client, "documents")
    loaders.load_companies(client, SEED_DIR)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_todos(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)

    # The anchor account (ANCHOR_COMPANIES in the generator): guaranteed to be
    # in every seed, with both a company row and notes of its own — which is
    # what makes this a cross-entity lookup rather than a document search.
    # Naming any other account couples the test to a random roster draw.
    res = search.quick_find(client, "genco")
    t.h1("quick-find 'genco' — grouped hits with open targets")
    for g in res["groups"]:
        for it in g["items"]:
            t.tln(f"  [{g['kind']}] {it['label']!r} -> {it['target']}")
    kinds = {g["kind"] for g in res["groups"]}
    assert "company" in kinds, "the anchor company node is found"
    assert any(it["target"] == "company/genco-oy"
               for g in res["groups"] for it in g["items"]), "with a deep-link target"
    assert any(g["kind"] == "note" for g in res["groups"]), "its notes are found too"
