"""The learning board: Build-Measure-Learn over the experiments table.

Two reads:
  - descriptive (counts → rate; formatting, not inference): the validated-
    learning rate (validated / decided), the status mix, and the live board
    of running bets with their hypothesis and target.
  - the predictive question, from Aito: *which kinds of experiment tend to
    pay off?* `_predict validated GIVEN effort` (and by area) — the seed
    plants the Lean doctrine that small, cheap bets validate more often than
    large ones, and the board should recover it.

Honest cold start: with few decided experiments the rates and the predicted
P(validated) are weak and wide. That is the loop working, not failing — the
substrate accrues as bets are logged and resolved.
"""

from dataclasses import dataclass, field

from . import schema
from .aito import AitoClient


@dataclass
class Result:
    calls: list[tuple[str, dict, dict]] = field(default_factory=list)
    derived: dict | None = None


def _count(client: AitoClient, result: Result, where: dict) -> int:
    request = {"from": "experiments", "where": where, "limit": 0}
    response = client.query(request)
    result.calls.append(("_query", request, response))
    return response["total"]


def _p_validated(client: AitoClient, result: Result, where: dict) -> float | None:
    request = {"from": "experiments", "where": where, "predict": "validated",
               "select": ["$p", "$value"]}
    response = client.predict(request)
    result.calls.append(("_predict", request, response))
    hit = next((h for h in response["hits"] if h["$value"] is True), None)
    return hit["$p"] if hit else None


def _running(client: AitoClient, result: Result) -> list[dict]:
    request = {"from": "experiments", "where": {"status": "running"}, "limit": 50}
    response = client.query(request)
    result.calls.append(("_query", request, response))
    rows = sorted(response["hits"], key=lambda e: e.get("started", ""))
    return [{"experiment_id": e["experiment_id"], "area": e["area"],
             "type": e["type"], "effort": e["effort"], "metric": e["metric"],
             "baseline": e["baseline"], "target": e["target"],
             "hypothesis": e["hypothesis"], "started": e["started"]} for e in rows]


def board(client: AitoClient) -> Result:
    result = Result()
    total = _count(client, result, {})
    if not total:
        result.derived = {"total": 0, "running": [], "decided": 0,
                          "validated_learning_rate": None, "status_mix": {},
                          "by_effort": [], "favour_small": None}
        return result

    status_mix = {s: _count(client, result, {"status": s})
                  for s in sorted(schema.EXPERIMENT_STATUS)}
    decided = sum(status_mix[s] for s in schema.EXPERIMENT_TERMINAL)
    validated = status_mix["validated"]

    by_effort = []
    for effort in ("small", "medium", "large"):
        n_val = _count(client, result, {"effort": effort, "status": "validated"})
        n_dec = sum(_count(client, result, {"effort": effort, "status": s})
                    for s in schema.EXPERIMENT_TERMINAL)
        by_effort.append({
            "effort": effort, "decided": n_dec, "validated": n_val,
            "observed": (n_val / n_dec) if n_dec else None,
            "aito_p": _p_validated(client, result, {"effort": effort}) if n_dec else None,
        })

    # the Lean read: do cheaper bets validate more? (small >= large, with data)
    obs = {b["effort"]: b["observed"] for b in by_effort}
    favour_small = (obs["small"] is not None and obs["large"] is not None
                    and obs["small"] > obs["large"])

    result.derived = {
        "total": total,
        "running": _running(client, result),
        "decided": decided,
        "validated_learning_rate": (validated / decided) if decided else None,
        "status_mix": status_mix,
        "by_effort": by_effort,
        "favour_small": favour_small,
    }
    return result
