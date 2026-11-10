"""Funnel gate: the predictive funnel data layer on both datasets.

Snapshots the stage counts, step conversion, the leak, Aito's
outlook + $why, causes, and lever for both funnels (website over sessions,
sales over contacts) on seed, a couple of slices, and the cold-start tiny
set. The HTML carries no logic; this data layer is where correctness is
checked. Requires a running Aito instance.
"""

import json

import booktest as bt

from company_ai import funnels, loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, SEED_TINY_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _load(client: AitoClient, data_dir) -> None:
    loaders.create_schema(client)
    loaders.load_rolodex(client, data_dir)
    loaders.load_touches(client, data_dir)
    loaders.load_sessions(client, data_dir)


def _print(t: bt.TestCaseRun, result: funnels.Result) -> None:
    d = result.derived
    t.h2("Aito calls")
    for endpoint, request, _ in result.calls:
        t.tln(f"{endpoint}: {json.dumps(request, sort_keys=True)}")
    t.h2("Derived")
    for s in d["stages"]:
        conv = "" if s["conversion_from_prev"] is None else f"  ({s['conversion_from_prev']:.4f} from prev)"
        t.tln(f"  {s['label']}: {s['count']}  rate_of_top={s['rate_of_top']:.4f}{conv}")
    t.tln(f"  leak: {d['leak']}")
    t.tln(f"  outlook P({d['deepest_label']}) = {d['outlook']['p']:.4f}")
    for w in d["outlook"]["why"]:
        t.tln(f"    why {w['field']}={w['value']} lift={w['lift']:.4f}")
    for c in d["causes"]:
        t.tln(f"    cause {c['field']}={c['value']} with={c['rate_with']:.4f} "
              f"without={c['rate_without']:.4f} mi={c['mi']:.4f}")
    if d["lever"]:
        opts = ", ".join(f"{o['value']}={o['p']:.4f}" for o in d["lever"]["options"])
        t.tln(f"    lever {d['lever']['field']}: {opts}")


def test_website_funnel_seed(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client, SEED_DIR)
    t.h1("Website funnel: all sessions")
    _print(t, funnels.funnel(client, "website", {}))
    t.h1("Website funnel: source=referral")
    _print(t, funnels.funnel(client, "website", {"source": "referral"}))
    t.h1("Website funnel: device=mobile (the planted trial leak)")
    _print(t, funnels.funnel(client, "website", {"device": "mobile"}))


def test_sales_funnel_seed(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client, SEED_DIR)
    t.h1("Sales funnel: all contacts")
    _print(t, funnels.funnel(client, "sales", {}))
    t.h1("Sales funnel: segment=accounting")
    _print(t, funnels.funnel(client, "sales", {"segment": "accounting"}))


def test_funnels_seed_tiny(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client, SEED_TINY_DIR)
    t.h1("Website funnel, tiny dataset (cold-start honesty)")
    _print(t, funnels.funnel(client, "website", {}))
    t.h1("Sales funnel, tiny dataset")
    _print(t, funnels.funnel(client, "sales", {}))


def test_unknown_dimension_asserts(t: bt.TestCaseRun) -> None:
    t.h1("Unknown funnel and unknown dimension both raise")
    for label, fn in {
        "unknown funnel": lambda: funnels.funnel(_client(), "revenue", {}),
        "unknown dimension": lambda: funnels.funnel(_client(), "website", {"plan": "pro"}),
    }.items():
        try:
            fn()
            raise RuntimeError(f"{label}: was accepted")
        except AssertionError as e:
            t.tln(f"{label}: {e}")


def test_a_funnel_over_an_empty_table_says_so(t: bt.TestCaseRun) -> None:
    """The website funnel reads the synthetic `sessions` table. On an instance
    where it holds nothing (internal: the real visits are in web_sessions), the
    funnel must say so rather than answer every stage with zero (rule 3)."""
    from book._target import guarded_client
    client = guarded_client()   # it deletes a table: refuse anything but a test env
    client.delete_table("sessions")
    loaders.create_schema(client)
    t.h1("funnel('website') with `sessions` empty")
    try:
        funnels.funnel(client, "website", {})
    except AssertionError as e:
        t.tln(f"  raises: {e}")
    else:
        raise AssertionError("an empty funnel table must raise, not answer zeros")
    _load(client, SEED_DIR)     # leave the seed as the other cases expect it


def test_the_web_funnel_reads_real_visits_as_reach(t: bt.TestCaseRun) -> None:
    """funnel("web") is aito.ai's real traffic (web_sessions, bots out); the
    "website" funnel stays the demo's synthetic one. The web flags aren't
    ordered (a visitor can click sign-up without seeing pricing), so each stage
    is its reach among human sessions, with no step conversion and no leak,
    plus one overlap row (CPO, 11.11.2026)."""
    from book.test_web_analytics import DAY, _clean, _events, _seeded
    from company_ai import webanalytics
    client, _, _ = _seeded()
    webanalytics.store_day(client, DAY, _events())
    rows = [r for r in client.query({"from": "web_sessions", "limit": 1000})["hits"] if not r["likely_bot"]]
    d = funnels.funnel(client, "web", {}).derived
    t.h1("funnel('web') over the fixture day")
    for s in d["stages"]:
        t.tln(f"  {s['label']}: {s['count']} ({s['rate_of_top']:.2f} of sessions), "
              f"conversion_from_prev {s['conversion_from_prev']}")
    t.tln(f"  ordered: {d['ordered']}, leak: {d['leak']}")
    t.tln(f"  overlap: {d['overlap']}")
    t.tln(f"  outlook P({d['deepest_label']}) = {d['outlook']['p']:.4f}")
    t.tln(f"  label: {d['label']}")
    want = {"Sessions": len(rows), "Onward click": sum(r["onward_click"] for r in rows),
            "Pricing page": sum(bool(r.get("kpi_pricing_page")) for r in rows),
            "Sign-up click": sum(r["signup_cta"] for r in rows)}
    assert {s["label"]: s["count"] for s in d["stages"]} == want, (d["stages"], want)
    assert d["ordered"] is False and d["leak"] is None
    assert all(s["conversion_from_prev"] is None for s in d["stages"]), "no step conversion"
    both = sum(r["signup_cta"] and bool(r.get("kpi_pricing_page")) for r in rows)
    assert (d["overlap"]["of"], d["overlap"]["also"]) == (want["Sign-up click"], both)
    assert "real" in d["label"].lower() and "demo" in funnels.FUNNELS["website"].label.lower()
    _clean(client)
