"""Segment 360 gate: the dashboard's data layer on both datasets.

The HTML rendering carries no logic, so it is the one surface not under
booktest; everything numeric the dashboard shows is analytics.segment_360
output, snapshotted here. Requests and the derived rates/causes/levers are
printed for review. as_of-independent: the 360 reads the whole touch
history.
"""

import json

import booktest as bt

from company_ai import analytics, loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, SEED_TINY_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _load(client: AitoClient, data_dir) -> None:
    loaders.create_schema(client)
    loaders.load_rolodex(client, data_dir)
    loaders.load_touches(client, data_dir)


def _print_360(t: bt.TestCaseRun, result: analytics.Result) -> None:
    t.h2("Aito calls")
    for endpoint, request, _ in result.calls:
        t.tln(f"{endpoint}: {json.dumps(request, sort_keys=True)}")
    t.h2("Derived")
    for kpi in result.derived["kpis"]:
        t.tln(f"[{kpi['label']}] rate={kpi['rate']:.4f}  (good = {kpi['good_when_true']})")
        for w in kpi["why"]:
            t.tln(f"    why  {w['field']}={w['value']}  lift={w['lift']:.4f}")
        for c in kpi["causes"]:
            t.tln(f"    cause {c['field']}={c['value']}  "
                  f"with={c['rate_with']:.4f} without={c['rate_without']:.4f} mi={c['mi']:.4f}")
        lever = kpi["lever"]
        opts = ", ".join(f"{o['value']}={o['p']:.4f}" for o in lever["options"])
        lift = f"{lever['lift']:.2f}" if lever["lift"] else "n/a"
        t.tln(f"    lever {lever['field']} (lift {lift}): {opts}")


def test_360_seed(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client, SEED_DIR)
    t.h1("360: whole pipeline (all contacts)")
    _print_360(t, analytics.segment_360(client, {}))
    t.h1("360: segment=accounting")
    _print_360(t, analytics.segment_360(client, {"segment": "accounting"}))
    t.h1("360: segment=erp, tier=A")
    _print_360(t, analytics.segment_360(client, {"segment": "erp", "tier": "A"}))


def test_360_seed_tiny(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client, SEED_TINY_DIR)
    t.h1("360: whole pipeline, tiny dataset (cold-start honesty)")
    _print_360(t, analytics.segment_360(client, {}))


def test_unknown_dimension_asserts(t: bt.TestCaseRun) -> None:
    t.h1("Unknown segment dimension raises (no silent drop)")
    try:
        analytics.segment_360(_client(), {"industry": "saas"})
        raise RuntimeError("unknown dimension was accepted")
    except AssertionError as e:
        t.tln(str(e))
