"""One account unfolded (docs/41, td-20260926220007895967): the company, its
people, deals, notes, touches and active facts as one graph; every fact linked
to the record it came from, or named as external or dangling; and the
harvested node facts carrying the rows they were derived from. Requires a
running Aito instance."""

from datetime import date

import booktest as bt

from company_ai import graph, loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

FACTS = loaders._read_csv(SEED_DIR / "facts.csv")
REPLICA = FACTS[0]["company"]
RID = loaders.company_slug(REPLICA)


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _seeded() -> AitoClient:
    client = _client()
    loaders.create_schema(client)
    loaders.load_all(client, SEED_DIR)
    return client


def _ids(client: AitoClient, table: str, key: str, where: dict) -> set[str]:
    return {h[key] for h in client.query({"from": table, "where": where, "select": [key],
                                          "limit": 100000})["hits"]}


def test_one_account_unfolds_into_its_own_records(t: bt.TestCaseRun) -> None:
    client = _seeded()
    net = graph.network(client, focus=RID)
    t.h1("network(focus=<replica>)")
    t.tln(f"  nodes: {net['counts']}")
    t.tln(f"  edges: {dict(sorted(_edge_kinds(net).items()))}")
    t.h2("The requests")
    for r in net["requests"]:
        t.tln(f"  {r['from']}: where {r.get('where')}")
    by_kind: dict[str, set[str]] = {}
    for n in net["nodes"]:
        by_kind.setdefault(n["kind"], set()).add(n["id"].split(":", 1)[1])
    assert by_kind["company"] == {RID}
    assert by_kind["contact"] == _ids(client, "contacts", "contact_id", {"company_id": RID})
    assert by_kind["deal"] == _ids(client, "deals", "deal_id", {"company_id": RID})
    assert by_kind["document"] == _ids(client, "documents", "doc_id", {"company_id": RID})
    assert by_kind["touch"] == _ids(client, "touches", "touch_id", {"contact_id.company_id": RID})
    active = {f["fact_id"] for f in FACTS if f["company"] == REPLICA and not f["superseded_by"]}
    assert by_kind["fact"] == active, "exactly the active facts"
    superseded = {f["fact_id"] for f in FACTS if f["company"] == REPLICA and f["superseded_by"]}
    assert superseded and not superseded & by_kind["fact"]
    t.tln(f"  superseded facts left out: {sorted(superseded)}")
    assert all(e["source"] in {n["id"] for n in net["nodes"]} and
               e["target"] in {n["id"] for n in net["nodes"]} for e in net["edges"])

    t.h1("Without focus, the graph is unchanged: no touches or facts")
    whole = graph.network(client)
    t.tln(f"  kinds: {sorted(whole['counts'])}")
    assert not {"touch", "fact"} & set(whole["counts"])


def test_every_fact_says_where_it_came_from(t: bt.TestCaseRun) -> None:
    client = _seeded()
    net = graph.network(client, focus=RID)
    nodes = {n["id"]: n for n in net["nodes"]}
    said_in = {e["source"]: e["target"] for e in net["edges"] if e["kind"] == "said_in"}
    t.h1("Each fact and its source")
    for n in (n for n in net["nodes"] if n["kind"] == "fact"):
        src = n["source"]
        t.tln(f"  {n['id']}: {src['kind']}:{src['id']} -> {src['status']}"
              + (f" ({said_in[n['id']]})" if n["id"] in said_in else ""))
        assert src["status"] in ("linked", "external", "dangling"), src
        assert (src["status"] == "linked") == (n["id"] in said_in)
        if src["status"] == "linked":
            assert said_in[n["id"]] in nodes
    seed_kinds = {f"fact:{f['fact_id']}": f["source_kind"] for f in FACTS if f["company"] == REPLICA}
    stored = [nid for nid, k in seed_kinds.items() if k in ("doc", "touch") and nid in nodes]
    assert stored and all(nodes[nid]["source"]["status"] == "linked" for nid in stored), \
        "the seed's doc and touch facts point at real records"

    t.h1("add_fact with a source that isn't stored: accepted, warned, drawn dangling")
    row = log.add_fact(client, company=REPLICA, kind="decision", statement="Budget moved to Q1",
                       source_kind="doc", source_id="doc-nope", valid_from="2026-11-06", author="cro")
    t.tln(f"  warnings: {row['warnings']}")
    assert row["warnings"] == ["source doc:doc-nope not found"]
    node = next(n for n in graph.network(client, focus=RID)["nodes"] if n["id"] == f"fact:{row['fact_id']}")
    t.tln(f"  in the unfold: {node['source']['status']}")
    assert node["source"]["status"] == "dangling"

    t.h1("A call logged as a touch links to it")
    touch = sorted(_ids(client, "touches", "touch_id", {"contact_id.company_id": RID}))[0]
    row = log.add_fact(client, company=REPLICA, kind="open_question", slot="ours",
                       statement="Send the pilot scope", source_kind="call", source_id=touch,
                       valid_from="2026-11-06", author="cro")
    assert row["warnings"] == []
    net = graph.network(client, focus=RID)
    edge = next(e for e in net["edges"] if e["kind"] == "said_in" and e["source"] == f"fact:{row['fact_id']}")
    t.tln(f"  call -> {edge['target'] == f'touch:{touch}'}")
    assert edge["target"] == f"touch:{touch}"
    t.tln(f"  a mail source: {log.add_fact(client, company=REPLICA, kind='decision', statement='Mail decision', source_kind='mail', source_id='mail-x', valid_from='2026-11-06', author='cro')['warnings']}")


def test_the_harvested_facts_carry_their_rows(t: bt.TestCaseRun) -> None:
    client = _seeded()
    rows = loaders.companies_from_csvs(SEED_DIR)
    picks = [RID] + [next(r["company_id"] for r in rows if r["relationship"] == rel and r["company_id"] != RID)
                     for rel in ("customer", "none")]
    for cid in picks:
        company = next(n for n in graph.network(client, focus=cid)["nodes"] if n["kind"] == "company")
        t.h1(f"{company['facts']['relationship']} account")
        for field in ("industry", "country", "relationship", "mrr_eur"):
            b = company["basis"][field]
            t.tln(f"  {field} = {company['facts'][field]!r}: {b['why']} {sorted(b['rows'])}")
            assert b["value"] == company["facts"][field], (field, b, company["facts"][field])
            assert b["matches"] is True
    t.h1("A live write the harvest hasn't seen shows as a disagreement, not hidden")
    cid = picks[2]
    name = next(r["name"] for r in rows if r["company_id"] == cid)
    deal = log.add_deal(client, company=name, segment="other", stage="pilot", value_eur=1200,
                        probability=20, champion_present=False, as_of=date(2026, 11, 6))
    company = next(n for n in graph.network(client, focus=cid)["nodes"] if n["kind"] == "company")
    b = company["basis"]["relationship"]
    t.tln(f"  stored {company['facts']['relationship']!r}, its rows now say {b['value']!r}: matches={b['matches']}")
    assert company["facts"]["relationship"] == "none" and b["value"] == "prospect" and b["matches"] is False
    assert deal["deal_id"] in b["rows"]


def test_a_held_account_shows_its_hold(t: bt.TestCaseRun) -> None:
    client = _seeded()
    held = next(f for f in FACTS if f["kind"] == "hold")
    company = next(n for n in graph.network(client, focus=loaders.company_slug(held["company"]))["nodes"]
                   if n["kind"] == "company")
    t.h1("The held account's node")
    t.tln(f"  hold: {company['hold']}")
    assert company["hold"] == "HOLD"
    replica = next(n for n in graph.network(client, focus=RID)["nodes"] if n["kind"] == "company")
    assert replica["hold"] is None


def _edge_kinds(net: dict) -> dict:
    out: dict[str, int] = {}
    for e in net["edges"]:
        out[e["kind"]] = out.get(e["kind"], 0) + 1
    return out
