"""Deals gate: the pipeline, close-likelihood, and the closed-loop write.

Snapshots the weighted pipeline + per-deal Aito close-likelihood on both
datasets, and proves the closed loop: logging a deal update re-ranks the
pipeline (the deals analog of the sacred round-trip). Requires a running
Aito instance.
"""

import json
from datetime import date

import booktest as bt

from company_ai import deals, loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, SEED_TINY_DIR, Config

AS_OF = date(2026, 6, 14)


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _load(client: AitoClient, data_dir) -> None:
    loaders.create_schema(client)
    loaders.load_deals(client, data_dir)


def _print(t: bt.TestCaseRun, result) -> None:
    d = result.derived
    k = d["kpis"]
    t.tln(f"weighted={k['weighted_pipeline']} open_value={k['open_value']} "
          f"open={k['open_deals']} stalled={k['stalled']}")
    for x in d["deals"]:
        pw = f"{x['p_win']:.4f}" if x["p_win"] is not None else "n/a"
        why = x["why"][0]["label"] if x["why"] else ""
        t.tln(f"  w={x['weighted_value']:>6} {x['stage']:11} own={x['probability']:>3} "
              f"Aito={pw} {'STALL' if x['stalled'] else '    '} {why}")


def test_pipeline_seed(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client, SEED_DIR)
    t.h1("Pipeline + close-likelihood, seed")
    _print(t, deals.pipeline(client, as_of=AS_OF))


def test_pipeline_seed_tiny(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client, SEED_TINY_DIR)
    t.h1("Pipeline, tiny dataset (cold-start)")
    _print(t, deals.pipeline(client, as_of=AS_OF))


def test_deal_update_round_trip(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client, SEED_DIR)
    before = deals.pipeline(client, as_of=AS_OF).derived
    top = before["deals"][0]
    t.h1("Before: weighted pipeline and the top deal")
    t.tln(f"weighted={before['kpis']['weighted_pipeline']} open={before['kpis']['open_deals']}")
    t.tln(f"top: {top['deal_id']} {top['company']} {top['stage']} w={top['weighted_value']}")

    t.h1("Close the top deal as won")
    row = log.log_deal_update(client, top["deal_id"], stage="closed_won", as_of=AS_OF)
    t.tln(json.dumps({k: row[k] for k in ("deal_id", "stage", "won")}, sort_keys=True))

    after = deals.pipeline(client, as_of=AS_OF).derived
    t.h1("After: the won deal has left the open pipeline")
    t.tln(f"weighted={after['kpis']['weighted_pipeline']} open={after['kpis']['open_deals']}")
    assert top["deal_id"] not in {d["deal_id"] for d in after["deals"]}, \
        "closed_won deal still in open pipeline"
    assert after["kpis"]["open_deals"] == before["kpis"]["open_deals"] - 1, \
        "open deal count did not drop by one"
    t.tln(f"confirmed: {top['deal_id']} left the open pipeline, "
          f"open {before['kpis']['open_deals']} -> {after['kpis']['open_deals']}")


def test_unknown_stage_asserts(t: bt.TestCaseRun) -> None:
    t.h1("An unknown deal stage raises")
    good = {
        "deal_id": "x", "company": "Acme Oy", "segment": "accounting",
        "stage": "lead", "value_eur": "20000", "probability": "40",
        "champion_present": "true", "blocker": "none",
        "last_touch_date": "2026-06-01", "created": "2026-01-01",
    }
    try:
        loaders.parse_deal_row({**good, "stage": "closed_maybe"})
        raise RuntimeError("accepted an unknown stage")
    except AssertionError as e:
        t.tln(str(e))


def test_who_to_reach_traverses_the_company_graph(t: bt.TestCaseRun) -> None:
    """The entity graph (.ai/tasks/15): contacts, companies, and deals link on
    `company_id`, so "who to reach at companies with a stalled deal, ranked by
    close-likelihood" is one relational pass, not a hand-joined string. Pins the
    link traversal and the marquee query."""
    client = _client()
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)   # link target, loaded first
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)

    t.h1("the company_id link resolves the entity (contacts -> companies)")
    hit = client.query({"from": "contacts", "limit": 1,
                        "select": ["name", "company", "company_id", "company_id.name"]})["hits"][0]
    t.tln(f"contact {hit['name']}: company='{hit['company']}' "
          f"company_id='{hit['company_id']}' -> company_id.name='{hit['company_id.name']}'")
    assert hit["company_id.name"] == hit["company"], "the link resolves back to the company name"

    t.h1("who_to_reach: stalled deals ranked by close-likelihood + the people at each")
    res = deals.who_to_reach(client, as_of=AS_OF, top_n=3).derived
    t.tln(f"stalled companies: {res['count']}")
    for r in res["rows"]:
        who = ", ".join(f"{p['name']} ({p['role']})" for p in r["contacts"][:2])
        t.tln(f"  {r['company']} [{r['stage']}] p_win={r['p_win']:.2f} "
              f"quiet={r['days_since_touch']}d -> {who}")
    assert res["count"] >= 1
    assert all(r["contacts"] for r in res["rows"]), "each stalled company reachable via the link"
