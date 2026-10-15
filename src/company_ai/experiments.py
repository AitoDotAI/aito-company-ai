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

from . import history, schema
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
    # learned from decided experiments only (history.finished): a running bet
    # has no verdict, whatever its `validated` column reads
    request = {"from": history.finished("experiments"), "where": where,
               "predict": "validated", "select": ["$p", "$value"]}
    response = history.predict(client, request)
    if response is None:
        return None
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


def _p_validated_many(client: AitoClient, result: Result, wheres: list[dict]) -> list[float | None]:
    requests = [{"from": history.finished("experiments"), "where": w,
                 "predict": "validated", "select": ["$p", "$value"]} for w in wheres]
    responses = history.predict_many(client, requests)
    out = []
    for request, response in zip(requests, responses):
        if response is None:
            out.append(None)
            continue
        result.calls.append(("_predict", request, response))
        hit = next((h for h in response["hits"] if h["$value"] is True), None)
        out.append(hit["$p"] if hit else None)
    return out


def board(client: AitoClient) -> Result:
    """Three Aito requests whatever the vocabulary: one projected read that the
    counts are tallied from (accounting, not prediction), the running bets, and
    one _batch for the per-effort predictions (was a count query per status and
    per effort x status, plus a predict per effort; td-20261014123607349120)."""
    result = Result()
    request = {"from": "experiments", "select": ["status", "effort"], "limit": 100000}
    response = client.query(request)
    result.calls.append(("_query", request, response))
    rows = response["hits"]
    total = len(rows)
    if not total:
        result.derived = {"total": 0, "running": [], "decided": 0,
                          "validated_learning_rate": None, "status_mix": {},
                          "by_effort": [], "favour_small": None}
        return result

    status_mix = {s: sum(1 for r in rows if r["status"] == s)
                  for s in sorted(schema.EXPERIMENT_STATUS)}
    decided = sum(status_mix[s] for s in schema.EXPERIMENT_TERMINAL)
    validated = status_mix["validated"]

    efforts = ("small", "medium", "large")
    tallies = []
    for effort in efforts:
        n_val = sum(1 for r in rows if r.get("effort") == effort and r["status"] == "validated")
        n_dec = sum(1 for r in rows if r.get("effort") == effort
                    and r["status"] in schema.EXPERIMENT_TERMINAL)
        tallies.append((effort, n_val, n_dec))
    asked = [e for e, _, n_dec in tallies if n_dec]
    p_by_effort = dict(zip(asked, _p_validated_many(client, result, [{"effort": e} for e in asked])))
    by_effort = [{
        "effort": effort, "decided": n_dec, "validated": n_val,
        "observed": (n_val / n_dec) if n_dec else None,
        "aito_p": p_by_effort.get(effort),
    } for effort, n_val, n_dec in tallies]

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
