"""The dogfood scorecard: agent recommended → human did → was it right?

Reads the `decisions` log and answers two things:
  - descriptive: how often the operator accepts the agent, overall and by
    decision type (counts → rate; formatting, not inference)
  - the dogfood question, from Aito: *is the agent's confidence trustworthy?*
    `_predict accepted GIVEN confidence_bucket` — high-confidence
    recommendations should be accepted more than low-confidence ones. If the
    calibration is flat or inverted, the agent's confidence is noise.

Honest cold start: real decision history is thin (decisions are often prose,
not logged rows), so early rates and calibration are weak — correct, not a
bug. The substrate accrues as `log_decision` fires.
"""

from dataclasses import dataclass, field

from . import history, schema
from .aito import AitoClient

CONFIDENCE_BUCKETS = ["low", "medium", "high"]


@dataclass
class Result:
    calls: list[tuple[str, dict, dict]] = field(default_factory=list)
    derived: dict | None = None


def _count(client: AitoClient, result: Result, where: dict) -> int:
    request = {"from": "decisions", "where": where, "limit": 0}
    response = client.query(request)
    result.calls.append(("_query", request, response))
    return response["total"]


def _p_accepted(client: AitoClient, result: Result, where: dict) -> float | None:
    # The target is `human_action`, what the operator did, read as P(accepted),
    # over decisions with an action (history.finished). Not the derived
    # `accepted` Boolean: a decision logged before that column existed reads
    # null (or, on the July v2 build, False) though its human_action says
    # accepted, and would teach "not accepted".
    request = {"from": history.finished("decisions"), "where": where,
               "predict": "human_action", "select": ["$p", "$value"]}
    response = history.predict(client, request)
    if response is None:
        return None
    result.calls.append(("_predict", request, response))
    hit = next((h for h in response["hits"] if h["$value"] == "accepted"), None)
    return hit["$p"] if hit else None


def scorecard(client: AitoClient) -> Result:
    result = Result()
    total = _count(client, result, {})
    if not total:
        result.derived = {"total": 0, "acceptance": None, "by_type": [],
                          "calibration": [], "trustworthy": None}
        return result

    accepted = _count(client, result, {"human_action": "accepted"})
    by_type = []
    for dt in sorted(schema.DECISION_TYPES):
        n = _count(client, result, {"decision_type": dt})
        a = _count(client, result, {"decision_type": dt, "human_action": "accepted"})
        by_type.append({"type": dt, "n": n, "accepted": a,
                        "rate": (a / n) if n else None})

    calibration = []
    for bucket in CONFIDENCE_BUCKETS:
        n = _count(client, result, {"confidence_bucket": bucket})
        a = _count(client, result, {"confidence_bucket": bucket, "human_action": "accepted"})
        calibration.append({
            "bucket": bucket, "n": n,
            "observed": (a / n) if n else None,
            "aito_p": _p_accepted(client, result, {"confidence_bucket": bucket}) if n else None,
        })

    # trustworthy if observed acceptance rises low -> high (monotone, with data)
    obs = [c["observed"] for c in calibration if c["observed"] is not None]
    trustworthy = len(obs) >= 2 and all(x <= y for x, y in zip(obs, obs[1:]))

    result.derived = {
        "total": total, "accepted": accepted, "acceptance": accepted / total,
        "by_type": by_type, "calibration": calibration, "trustworthy": trustworthy,
    }
    return result
