"""Recall gate (docs/40, slice 3 of td-20261103224048158692): active facts are
searchable, superseded ones never surface (and never shorten a page),
add_fact lists supersede candidates without applying them, the marks log on
the shown impression without moving the ranking, and a document under 500
characters is flagged thin without being re-ranked. Requires a running Aito
instance.
"""

import booktest as bt

from company_ai import companies, documents, loaders, log, schema, search
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

SEED = loaders._read_csv(SEED_DIR / "facts.csv")
REPLICA = SEED[0]["company"]


def F(n: int) -> str:
    return SEED[n - 1]["fact_id"]


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _seeded() -> AitoClient:
    client = _client()
    loaders.create_schema(client)
    loaders.load_all(client, SEED_DIR)
    for table in ("search_impressions", "search_contexts"):
        client.delete_table(table)
        AitoClient._ensured.discard(table)
    search.build_index(client)
    return client


def test_facts_are_searchable_and_superseded_ones_never_surface(t: bt.TestCaseRun) -> None:
    client = _seeded()
    t.h1("An active fact is found as kind fact")
    hits = search.search(client, "plugin decision mail", top_n=5).derived["hits"]
    t.tln(f"  {[(h['kind'], h['source_id']) for h in hits]}")
    assert ("fact", F(3)) in [(h["kind"], h["source_id"]) for h in hits]

    t.h1("A superseded fact is not")
    hits = search.search(client, "decision expected from the founder", kind="fact", top_n=10).derived["hits"]
    t.tln(f"  {[h['source_id'] for h in hits]}")
    assert F(11) not in [h["source_id"] for h in hits], "fact 11 is superseded by fact 3"

    t.h1("A query whose best matches are superseded still fills the page")
    # the four oldest match every query term and the four newest only one, so
    # unfiltered, the superseded four would take the whole page
    words = ["quokka budget decision"] * 4 + ["quokka note"] * 4
    made = [log.add_fact(client, company=REPLICA, kind="decision", statement=f"{w} {i}",
                         source_kind="call", source_id=f"call-q{i}", valid_from=f"2026-11-0{i + 1}",
                         author="cro")["fact_id"] for i, w in enumerate(words)]
    for old, new in zip(made[:4], made[4:]):
        log.supersede_fact(client, old, new)
    search.refresh(client)
    unfiltered = client.query({"from": "search_items",
                               "where": {"$and": [{"kind": "fact"}, search._match_clause("quokka budget decision")]},
                               "orderBy": {"$similarity": {"content": "quokka budget decision"}},
                               "select": ["source_id"], "limit": 4})["hits"]
    t.tln(f"  unfiltered, the top 4 are the superseded four: {[h['source_id'] for h in unfiltered] == made[:4]}")
    assert {h["source_id"] for h in unfiltered} == set(made[:4])
    page = search.search(client, "quokka budget decision", kind="fact", top_n=4).derived["hits"]
    t.tln(f"  top 4 of 8 matching (4 superseded): {len(page)} hits, all active: "
          f"{all(h['source_id'] in made[4:] for h in page)}")
    assert len(page) == 4 and {h["source_id"] for h in page} == set(made[4:])
    served = search.serve(client, "quokka budget decision", kind="fact", top_n=4, log=False)
    assert len(served["hits"]) == 4 and {h["source_id"] for h in served["hits"]} == set(made[4:])


def test_add_fact_lists_supersede_candidates_and_applies_none(t: bt.TestCaseRun) -> None:
    client = _seeded()
    row = log.add_fact(client, company=REPLICA, kind="role", slot="decision_owner",
                       statement="Commercial lead still owns the commercial track",
                       source_kind="mail", source_id="mail-c1", valid_from="2026-11-06",
                       author="cro", stakeholder_id=SEED[0]["stakeholder_id"])
    cands = row["supersede_candidates"]
    t.h1("A third decision owner: the two before it are the candidates, in Aito's order")
    for c in cands:
        t.tln(f"  {c['fact_id']}: {c['statement']} (text match: {c['text_match']})")
    assert [c["fact_id"] for c in cands][:1] == [F(1)], "the matching statement first"
    assert {c["fact_id"] for c in cands} == {F(1), F(2)}, "same company, kind and slot only"
    assert len(cands) <= 5
    active = {f["fact_id"] for f in companies.briefing(client, REPLICA).derived["facts"]["roles"]["decision_owner"]
              for f in [{"fact_id": f["source"]["id"]}]}
    assert {F(1), F(2), row["fact_id"]} <= active, "nothing is applied"
    t.tln("  all three still active: nothing applied")
    decision = log.add_fact(client, company=REPLICA, kind="decision", statement="Budget approved",
                            source_kind="mail", source_id="mail-c2", valid_from="2026-11-06", author="cro")
    t.tln(f"  a decision's candidates: {[c['fact_id'] for c in decision['supersede_candidates']]}")
    assert {c["fact_id"] for c in decision["supersede_candidates"]} == {F(3)}, \
        "superseded fact 11 is not a candidate"


def test_marks_log_on_the_shown_impression_and_move_nothing(t: bt.TestCaseRun) -> None:
    client = _seeded()
    q = "pilot scope"
    first = search.serve(client, q, top_n=5, source="mcp", company_id=loaders.company_slug(REPLICA))
    order = [h["item_id"] for h in first["hits"]]
    t.h1("Serve, click the third hit, then mark the first used and the second wrong")
    t.tln(f"  served {len(order)} hits")
    assert len(order) >= 3
    # a click first, so the learned _recommend ranks the next serve: marks then
    # have a trained ranking they could move, and the baseline is click-only
    search.record_click(client, first["context_id"], order[2])
    baseline = search.serve(client, q, top_n=5, log=False)
    assert baseline["learned"], "the click must turn the learned ranking on"
    base_order = [h["item_id"] for h in baseline["hits"]]
    t.tln(f"  after the click the clicked hit leads: {base_order[0] == order[2]}")
    search.mark_item(client, first["context_id"], order[0], used=True)
    search.mark_item(client, first["context_id"], order[1], flagged_wrong=True)
    rows = client.query({"from": "search_impressions", "where": {"context_id": first["context_id"]},
                         "limit": 100})["hits"]
    shown = [r for r in rows if not r["clicked"]]
    marked = {r["item_id"]: (r.get("used"), r.get("flagged_wrong")) for r in shown}
    t.tln(f"  impressions for the context: {len(shown)} shown + 1 click (none appended by marks)")
    assert len(shown) == len(order) and len(rows) == len(order) + 1
    assert marked[order[0]] == (True, None) and marked[order[1]] == (None, True)
    ctx = client.query({"from": "search_contexts", "where": {"context_id": first["context_id"]},
                        "limit": 1})["hits"][0]
    assert ctx["company_id"] == loaders.company_slug(REPLICA)
    t.tln("  the context records the account")
    again = search.serve(client, q, top_n=5, log=False)
    t.tln(f"  next serve, same order as the click-only baseline: {[h['item_id'] for h in again['hits']] == base_order}")
    assert again["learned"] and [h["item_id"] for h in again["hits"]] == base_order, "marks are logging only"

    t.h1("Refused marks")
    for label, call in (
            ("an item not shown", lambda: search.mark_item(client, first["context_id"], "doc:nope", used=True)),
            ("an unknown context", lambda: search.mark_item(client, "ctx_nope", order[0], used=True)),
            ("a mark that isn't a bool", lambda: search.mark_item(client, first["context_id"], order[0], used="yes")),
            ("no mark at all", lambda: search.mark_item(client, first["context_id"], order[0]))):
        try:
            call()
            raise AssertionError(f"{label} must be refused")
        except AssertionError as e:
            if "must be refused" in str(e):
                raise
            t.tln(f"  {label}: {str(e).replace(first['context_id'], 'ctx_<new>')}")


def test_code_before_schema_keeps_search_working(t: bt.TestCaseRun) -> None:
    """The release can reach an instance before create-schema adds the docs/40
    columns. Plain searches must keep logging; the new calls say what's missing."""
    client = _seeded()
    old_contexts = {**schema.SEARCH_CONTEXTS, "columns": {
        k: v for k, v in schema.SEARCH_CONTEXTS["columns"].items() if k != "company_id"}}
    old_impressions = {**schema.SEARCH_IMPRESSIONS, "columns": {
        k: v for k, v in schema.SEARCH_IMPRESSIONS["columns"].items() if k not in ("used", "flagged_wrong")}}
    client.create_table("search_contexts", old_contexts)
    client.create_table("search_impressions", old_impressions)
    t.h1("search_contexts and search_impressions as they are before the docs/40 columns")
    served = search.serve(client, "pilot scope", top_n=3, source="mcp")
    t.tln(f"  a plain search logs: {len(served['hits'])} hits, context logged: {served['context_id'].startswith('ctx_')}")
    item = served["hits"][0]["item_id"]
    search.record_click(client, served["context_id"], item)
    t.tln("  a click records")
    for label, call in (
            ("a search for an account",
             lambda: search.serve(client, "pilot scope", top_n=3, source="mcp", company_id="acme")),
            ("a mark", lambda: search.mark_item(client, served["context_id"], item, used=True))):
        try:
            call()
            raise AssertionError(f"{label} must be refused before the schema")
        except AssertionError as e:
            if "must be refused" in str(e):
                raise
            t.tln(f"  {label}: {e}")
    for table in ("search_impressions", "search_contexts"):
        client.delete_table(table)
        AitoClient._ensured.discard(table)


def test_a_short_document_is_flagged_thin_and_keeps_its_rank(t: bt.TestCaseRun) -> None:
    client = _seeded()
    seed_docs = loaders._read_csv(SEED_DIR / "documents.csv")
    short = min((d for d in seed_docs if d["company"]), key=lambda d: len(d["body"]))
    # every seed note is a short synthetic one, so the book adds one real-length note
    long_ = log.add_document(client, title="Quarterly account review notes", kind="internal",
                             area="sales", body="A full account review. " * 40)
    t.h1(f"THIN_DOC_CHARS = {schema.THIN_DOC_CHARS}")
    t.tln(f"  shortest seed note on an account: {len(short['body'])} chars; the added note: {len(long_['body'])}")
    assert len(short["body"]) < schema.THIN_DOC_CHARS <= len(long_["body"])
    hits = search.search(client, short["title"], kind="doc", top_n=5).derived["hits"]
    thin = {h["source_id"]: h["thin"] for h in hits}
    shown = [("<added note>" if h["source_id"] == long_["doc_id"] else h["source_id"], h["thin"]) for h in hits]
    t.tln(f"  search hits: {shown}")
    assert thin[short["doc_id"]] is True and hits[0]["source_id"] == short["doc_id"], \
        "flagged, and still ranked first for its own title"
    feed = {d["doc_id"]: d["thin"] for d in documents.feed(client).derived["documents"]}
    assert feed[short["doc_id"]] is True and feed[long_["doc_id"]] is False
    notes = companies.briefing(client, short["company"]).derived["notes"]
    assert next(n["thin"] for n in notes if n["source"]["id"] == short["doc_id"]) is True
    t.tln("  briefing notes carry it too")
    t.tln("  the feed carries it; nothing is hidden or re-ranked")
