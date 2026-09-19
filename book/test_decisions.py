"""Dogfood-scorecard gate: acceptance rates and the confidence-calibration
question (is the agent's confidence trustworthy?). The seed plants rising
acceptance with confidence; the scorecard should recover it. Requires Aito.
"""

import booktest as bt

from company_ai import decisions, loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, SEED_TINY_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _print(t: bt.TestCaseRun, d: dict) -> None:
    t.tln(f"total={d['total']} acceptance={d['acceptance']:.4f} trustworthy={d['trustworthy']}")
    for x in d["by_type"]:
        t.tln(f"  {x['type']:16} {x['accepted']}/{x['n']} = {x['rate']:.4f}")
    t.tln("  calibration (confidence -> P(accepted)):")
    for c in d["calibration"]:
        t.tln(f"    {c['bucket']:7} n={c['n']} observed={c['observed']:.4f} aito_p={c['aito_p']:.4f}")


def test_scorecard_seed(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_decisions(client, SEED_DIR)
    t.h1("Decision scorecard, seed")
    d = decisions.scorecard(client).derived
    _print(t, d)
    # the planted signal: acceptance rises with confidence
    obs = [c["observed"] for c in d["calibration"]]
    assert obs[0] < obs[-1], "low-confidence acceptance should be below high-confidence"
    assert d["trustworthy"], "calibration should read as trustworthy on the seed"


def test_scorecard_seed_tiny(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_decisions(client, SEED_TINY_DIR)
    t.h1("Decision scorecard, tiny dataset (cold-start — may be weak)")
    _print(t, decisions.scorecard(client).derived)
