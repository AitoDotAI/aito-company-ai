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
