"""Impressions loop (docs/23, phase 2 / A+C): serving a search logs a context +
impressions server-side; clicks train the ranking; a re-serve reflects them.
The round-trip is sacred — an operator's click must visibly change the next
ranking (rule 4: the repeatedly-clicked item outranks the text-match favourite).
Requires a running Aito instance.
"""

import booktest as bt

from company_ai import loaders, schema, search
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _reset_impressions(client: AitoClient) -> None:
    # linked child-first drop, parent-first create (Aito refuses to drop a table
    # linked into): impressions -> contexts.
    for tbl in ("search_impressions", "search_contexts"):
        try:
            client.delete_table(tbl)
        except Exception:
            pass
    for tbl in ("search_contexts", "search_impressions"):
        client.create_table(tbl, schema.TABLES[tbl])


def _seed(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    search.build_index(client)
    _reset_impressions(client)


def test_serve_logs_impressions_and_click_flips(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed(client)

    t.h1("Serving a search logs a context + one impression per hit")
    served = search.serve(client, "accounting", top_n=5)
    ctx = served["context_id"]
    t.tln(f"hits: {served['count']}; learned (cold): {served['learned']}")
    t.tln(f"contexts: {client.count('search_contexts')}; "
          f"impressions: {client.count('search_impressions')}")
    assert client.count("search_impressions") == served["count"]

    t.h1("A click flips exactly its impression to clicked=true")
    target = served["hits"][1]["item_id"]
    search.record_click(client, ctx, target)
    clicked = client.query({"from": "search_impressions",
                            "where": {"clicked": True}, "limit": 100})["hits"]
    t.tln(f"clicked impressions: {len(clicked)}; on target: "
          f"{all(c['item_id'] == target for c in clicked)}")
    assert len(clicked) == 1 and clicked[0]["item_id"] == target


def test_clicks_change_the_next_ranking(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed(client)
    query = "accounting"

    cold = search.serve(client, query, top_n=8)
    target = cold["hits"][3]["item_id"]      # a mid-ranked text-match hit
    t.h1("The round trip: repeatedly clicking a mid-ranked hit lifts it to the top")
    t.tln(f"cold ranking (text-match), learned={cold['learned']}:")
    for i, h in enumerate(cold["hits"]):
        t.tln(f"  {i}. {h['item_id']}")
    t.tln(f"target to train (rank 3): {target}")

    # several sessions where the operator keeps clicking the target
    for _ in range(7):
        s = search.serve(client, query, top_n=8)
        search.record_click(client, s["context_id"], target)

    warm = search.serve(client, query, top_n=8)
    warm_ranks = {h["item_id"]: i for i, h in enumerate(warm["hits"])}
    t.tln(f"\nwarm ranking, learned={warm['learned']}:")
    for i, h in enumerate(warm["hits"]):
        t.tln(f"  {i}. {h['item_id']}{'   <- trained' if h['item_id'] == target else ''}")
    t.tln(f"\ntarget moved rank 3 -> {warm_ranks[target]}")
    assert warm["learned"], "the ranking should now be click-trained"
    assert warm_ranks[target] == 0, "the repeatedly-clicked item must rank first"


def test_dangling_click_raises(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed(client)
    t.h1("A click on an unknown context/item raises (rule 3)")
    try:
        search.record_click(client, "ctx_nope", "deal:nope")
        raise RuntimeError("was accepted")
    except AssertionError as e:
        t.tln(f"{e}")


def test_impressions_without_clicks_do_not_activate_learned(t: bt.TestCaseRun) -> None:
    """Regression (the f8c5eb7 defect): the learned re-rank must gate on real
    CLICKS, not on impressions — which `_log_impressions` writes on EVERY search.
    With impressions present and zero clicks it must stay OFF, so ranking stays
    query-dependent instead of collapsing to the near-constant `_recommend`
    ordering that once armed after the very first search of all time."""
    client = _client()
    _seed(client)

    t.h1("Serve two distinct queries — impressions accumulate, nobody clicks")
    search.serve(client, "accounting", top_n=5)
    search.serve(client, "release", top_n=5)
    imp = client.count("search_impressions")
    clk = client.query({"from": "search_impressions", "where": {"clicked": True},
                        "limit": 0})["total"]
    t.tln(f"impressions: {imp}; clicked: {clk}")

    t.h1("The learned pass stays OFF, and ranking is query-dependent")
    a = search.ranked(client, "accounting", top_n=5).derived
    b = search.ranked(client, "release", top_n=5).derived
    t.tln(f"'accounting' learned={a['learned']}: {[h['item_id'] for h in a['hits'][:3]]}")
    t.tln(f"'release'    learned={b['learned']}: {[h['item_id'] for h in b['hits'][:3]]}")

    assert imp > 0 and clk == 0
    assert not a["learned"] and not b["learned"], "learned must not activate on impressions alone"
    assert a["hits"] != b["hits"], "ranking must stay query-dependent without clicks"
