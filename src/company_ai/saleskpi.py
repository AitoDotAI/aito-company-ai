"""Sales KPI trends: win-rate by quarter and average cycle time.

Pure arithmetic over the deals table — counting won/closed per calendar
quarter and averaging (close_date - created) over won deals. No prediction
lives here (that is `deals.pipeline`'s `_predict` close-likelihood); this is
the deterministic accounting that fills the sales-analytics trend, the
counterpart to the marketing funnel's step conversions (rule 2).
"""

from datetime import date

from .aito import AitoClient

CLOSED_STAGES = ("closed_won", "closed_lost")


def _quarter(iso: str) -> tuple[int, int]:
    d = date.fromisoformat(iso)
    return d.year, (d.month - 1) // 3 + 1


def win_trend(client: AitoClient, last_n: int = 6) -> dict:
    """Win rate per calendar quarter (by close date = the closed deal's last
    touch), plus the overall win rate and the mean cycle time of won deals.
    Returns the most recent `last_n` quarters that have any closed deal."""
    rows = client.query({"from": "deals", "limit": 100000})["hits"]
    closed = [r for r in rows if r["stage"] in CLOSED_STAGES]

    by_q: dict[tuple[int, int], dict] = {}
    for r in closed:
        b = by_q.setdefault(_quarter(r["last_touch_date"]), {"won": 0, "closed": 0})
        b["closed"] += 1
        if r["stage"] == "closed_won":
            b["won"] += 1

    quarters = sorted(by_q)[-last_n:]
    series = [{
        "label": f"Q{q}·{y % 100:02d}", "won": by_q[(y, q)]["won"],
        "closed": by_q[(y, q)]["closed"],
        "win_rate": round(by_q[(y, q)]["won"] / by_q[(y, q)]["closed"], 3),
    } for (y, q) in quarters]

    won = [r for r in closed if r["stage"] == "closed_won"]
    cycles = [(date.fromisoformat(r["last_touch_date"]) - date.fromisoformat(r["created"])).days
              for r in won]
    return {
        "quarters": series,
        "win_rate": round(len(won) / len(closed), 3) if closed else 0.0,
        "avg_cycle_days": round(sum(cycles) / len(cycles)) if cycles else 0,
        "won": len(won), "closed": len(closed),
    }
