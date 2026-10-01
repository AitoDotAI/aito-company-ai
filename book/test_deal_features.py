"""P(won) conditions on the deal's own features, not just its blocker and champion
(td-20260930191344950920 item 2).

On the seed, closed deals win 39% in accounting and 12% in ecommerce, a bigger
spread than most blockers. Two otherwise identical deals in those segments must
not read one number. A feature value too few closed deals share (fewer than
MIN_PROFILE_EVIDENCE) is not evidence; it is listed in `thin`, not dropped silently.
"""

import booktest as bt

from company_ai import deals, history, loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _observed(client: AitoClient, segment: str) -> tuple[int, int]:
    won = client.query({"from": "deals", "limit": 0, "where": {
        "$and": [history.TERMINAL["deals"], {"segment": segment}, {"stage": "closed_won"}]}})["total"]
    _, closed = history.count(client, "deals", {"segment": segment})
    return won, closed["total"]


def test_segment_moves_p_win(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_deals(client, SEED_DIR)
    t.h1("Same blocker and champion, different segment")
    p = {}
    for segment in ("accounting", "ecommerce"):
        won, closed = _observed(client, segment)
        cl = deals.close_likelihood(client, "pilot", "none", True, segment=segment)
        p[segment] = cl["p_win"]
        t.tln(f"  {segment:10} observed {won}/{closed}  Aito p_win={cl['p_win']:.4f} "
              f"basis={cl['basis']} n={cl['n']} evidence={cl['evidence']}")
        assert "segment" in cl["evidence"], cl
    assert p["accounting"] > p["ecommerce"], f"segment did not move P(won): {p}"


def test_a_thin_feature_is_listed_not_used(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_deals(client, SEED_DIR)
    t.h1("A segment no closed deal has")
    without = deals.close_likelihood(client, "pilot", "none", True)
    thin = deals.close_likelihood(client, "pilot", "none", True, segment="robotics")
    t.tln(f"  no segment: p_win={without['p_win']:.4f} evidence={without['evidence']}")
    t.tln(f"  robotics:   p_win={thin['p_win']:.4f} evidence={thin['evidence']} thin={thin['thin']}")
    assert thin["thin"] == [{"feature": "segment", "value": "robotics", "n": 0}], thin
    assert "segment" not in thin["evidence"]
    assert thin["p_win"] == without["p_win"]
