"""Sales KPI trends (saleskpi.win_trend): win rate by quarter, the overall win
rate, and mean cycle time — pure arithmetic over the closed-deal history, the
deterministic counterpart to the marketing funnel's step conversions.
"""

import booktest as bt

from company_ai import loaders, saleskpi
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def test_win_trend_seed(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)

    d = saleskpi.win_trend(client)

    t.h1("overall")
    t.tln(f"win rate = {d['win_rate']}  ({d['won']}/{d['closed']} closed)  "
          f"avg cycle = {d['avg_cycle_days']}d")

    t.h1("win rate by quarter (most recent 6 with closed deals)")
    for q in d["quarters"]:
        t.tln(f"  {q['label']}: {q['won']}/{q['closed']} won  ->  win_rate {q['win_rate']}")

    assert d["closed"] > 0 and d["quarters"], "seed has closed deals"
    assert all(0.0 <= q["win_rate"] <= 1.0 for q in d["quarters"])
    assert d["avg_cycle_days"] > 0
