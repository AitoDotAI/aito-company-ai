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

from . import schema
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
    request = {"from": "decisions", "where": where, "predict": "accepted",
               "select": ["$p", "$value"]}
    response = client.predict(request)
    result.calls.append(("_predict", request, response))
    hit = next((h for h in response["hits"] if h["$value"] is True), None)
    return hit["$p"] if hit else None


def scorecard(client: AitoClient) -> Result:
    result = Result()
    total = _count(client, result, {})
    if not total:
        result.derived = {"total": 0, "acceptance": None, "by_type": [],
                          "calibration": [], "trustworthy": None}
        return result

    accepted = _count(client, result, {"accepted": True})
    by_type = []
    for dt in sorted(schema.DECISION_TYPES):
        n = _count(client, result, {"decision_type": dt})
        a = _count(client, result, {"decision_type": dt, "accepted": True})
        by_type.append({"type": dt, "n": n, "accepted": a,
                        "rate": (a / n) if n else None})

    calibration = []
    for bucket in CONFIDENCE_BUCKETS:
        n = _count(client, result, {"confidence_bucket": bucket})
        a = _count(client, result, {"confidence_bucket": bucket, "accepted": True})
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
