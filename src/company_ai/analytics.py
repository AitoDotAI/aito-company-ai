"""Segment 360: the dashboard's data layer.

Per KPI, three Aito calls, exactly as the aito-agent-demo Company 360 does:
  1. rate + $why  -> _predict on a derived boolean (schema.kpi_flags)
  2. root causes  -> _relate {$on: [goal, segment]} (within-segment drivers)
  3. the lever    -> _recommend {goal} (what most moves the good outcome)

Python here only assembles the request bodies from the KPI registry,
forwards them, and orders Aito's own returned statistics ($p, mutual
information). No rate, cause, or lever is computed here; all of it is
Aito's, which keeps the dashboard inside CLAUDE.md rule 2: the UI is a
view, the intuition stays in Aito. Spec in docs/07-dashboard.md.
"""

from dataclasses import dataclass, field

from . import aitowhy
from .aito import AitoClient

# the segment dimensions the operator can slice by (contact attributes)
SEGMENT_DIMENSIONS = ["segment", "tier", "ai_lifecycle", "source"]


@dataclass
class KPI:
    key: str
    label: str
    target: str  # a derived boolean column on touches
    lever: str  # the field _recommend ranks
    good_when_true: str  # human label for target=true


KPIS = [
    KPI("conversion", "Conversion", "good_outcome", "window",
        "outcome was conversation / meeting / callback"),
    KPI("reach", "Reach", "reached", "channel",
        "the contact responded at all"),
    KPI("meeting", "Meetings", "booked", "channel",
        "a meeting was booked"),
]

# A cause is only actionable if it is known BEFORE the call. So causes are
# drawn from an allowlist of predictor fields — the touch context you
# control and the contact attributes you know in advance — never from
# `outcome`, the derived KPI booleans, or the post-call `next_action`/
# `notes` (those would "explain" the outcome with the outcome). The fixed
# segment dimensions are subtracted per-slice.
ALLOWED_CAUSE_FIELDS = {
    "window", "weekday", "channel", "days_since_prev_touch",
    "contact_id.segment", "contact_id.tier", "contact_id.ai_lifecycle",
    "contact_id.source", "contact_id.country", "contact_id.role",
    "contact_id.notes_tags", "contact_id.phone_present", "contact_id.email_present",
}
_SEGMENT_FIELDS = {f"contact_id.{d}" for d in SEGMENT_DIMENSIONS}


@dataclass
class Result:
    calls: list[tuple[str, dict, dict]] = field(default_factory=list)
    derived: dict | None = None


def _segment_where(segment: dict[str, str]) -> dict:
    """Active segment filters as an Aito `where` over linked contact fields."""
    return {f"contact_id.{dim}": value for dim, value in segment.items() if value}


def _segment_proposition(where: dict) -> dict | None:
    """The segment as a single proposition for _relate's $on (which takes
    exactly two). None when no dimension is fixed (the 'All' slice)."""
    items = [{k: v} for k, v in where.items()]
    if not items:
        return None
    if len(items) == 1:
        return items[0]
    return {"$and": items}


def _rate(client: AitoClient, result: Result, kpi: KPI, where: dict) -> dict:
    request = {
        "from": "touches",
        "where": where,
        "predict": kpi.target,
        "select": ["$p", "$value", "$why"],
    }
    response = client.predict(request)
    result.calls.append(("_predict", request, response))
    hit = next((h for h in response["hits"] if h["$value"] is True), None)
    if hit is None:
        return {"rate": 0.0, "why": []}
    why = [
        {
            "field": list(f["proposition"])[0],
            "value": aitowhy.prop_value(f["proposition"]),
            "lift": f["value"],
        }
        for f in aitowhy.lift_factors(hit)
    ]
    return {"rate": hit["$p"], "why": sorted(why, key=lambda w: -abs(w["lift"] - 1.0))}


def _causes(client: AitoClient, result: Result, kpi: KPI, seg_prop: dict | None,
            top_n: int = 3) -> list[dict]:
    if seg_prop is None:
        # 'All' slice: relate to the goal over the whole population
        relate = {kpi.target: True}
    else:
        relate = {"$on": [{kpi.target: True}, seg_prop]}
    # limit must be generous: _relate enumerates every field=value condition,
    # including leaky ones (outcome, the derived booleans) that we filter out
    # below. Too small a limit can truncate a real cause out of the window.
    request = {"from": "touches", "relate": relate, "limit": 150}
    response = client.relate(request)
    result.calls.append(("_relate", request, response))

    causes = []
    for hit in response.get("hits", []):
        # v2 relate: the goal is `condition`, the co-occurring driver is
        # `related`; `info` is the mutual-info float; frequencies are in `fs`.
        related = hit.get("related", {})
        field_name = next(iter(related), None)
        if field_name not in ALLOWED_CAUSE_FIELDS or field_name in _SEGMENT_FIELDS:
            continue
        raw = related[field_name]
        fs = hit.get("fs", {})
        f, n = fs.get("f", 0), fs.get("n", 0)
        fc, foc = fs.get("fCondition", 0), fs.get("fOnCondition", 0)
        causes.append({
            "field": field_name,
            "value": raw.get("$has") if isinstance(raw, dict) else raw,
            "rate_with": (foc / f) if f else None,
            "rate_without": ((fc - foc) / (n - f)) if (n - f) else None,
            "mi": hit.get("info", 0.0),
        })
    # secondary keys make ties deterministic, so snapshots are stable
    causes.sort(key=lambda c: (-c["mi"], c["field"], str(c["value"])))
    return causes[:top_n]


def _lever(client: AitoClient, result: Result, kpi: KPI, where: dict) -> dict:
    request = {
        "from": "touches",
        "where": where,
        "recommend": kpi.lever,
        "goal": {kpi.target: True},
        "limit": 6,
    }
    response = client.recommend(request)
    result.calls.append(("_recommend", request, response))
    options = [
        {"value": h["$value"], "p": h["$p"]}
        for h in response.get("hits", [])
    ]
    best = options[0]["p"] if options else 0.0
    worst = options[-1]["p"] if options else 0.0
    return {
        "field": kpi.lever,
        "options": options,
        "lift": (best / worst) if worst else None,
    }


def kpi_read(client: AitoClient, kpi_key: str, segment: dict[str, str] | None = None) -> Result:
    """One KPI's rate + lever for a slice, no causes — two Aito calls
    instead of segment_360's nine. The morning brief uses this to cite the
    conversion read for a queued contact's segment without the full panel."""
    segment = {k: v for k, v in (segment or {}).items() if v}
    kpi = next((k for k in KPIS if k.key == kpi_key), None)
    assert kpi is not None, f"unknown kpi {kpi_key!r}; have {[k.key for k in KPIS]}"
    where = _segment_where(segment)
    result = Result()
    rate = _rate(client, result, kpi, where)
    lever = _lever(client, result, kpi, where)
    result.derived = {
        "key": kpi.key, "segment": segment,
        "rate": rate["rate"], "lever": lever,
    }
    return result


def segment_360(client: AitoClient, segment: dict[str, str] | None = None) -> Result:
    """Full 360 for a segment slice. `segment` keys are SEGMENT_DIMENSIONS;
    empty / omitted means the whole population (the 'All' slice)."""
    segment = {k: v for k, v in (segment or {}).items() if v}
    unknown = set(segment) - set(SEGMENT_DIMENSIONS)
    assert not unknown, f"unknown segment dimensions {sorted(unknown)}; allowed {SEGMENT_DIMENSIONS}"
    where = _segment_where(segment)
    seg_prop = _segment_proposition(where)
    result = Result()

    kpis = []
    for kpi in KPIS:
        rate = _rate(client, result, kpi, where)
        kpis.append({
            "key": kpi.key,
            "label": kpi.label,
            "target": kpi.target,
            "good_when_true": kpi.good_when_true,
            "rate": rate["rate"],
            "why": rate["why"],
            "causes": _causes(client, result, kpi, seg_prop),
            "lever": _lever(client, result, kpi, where),
        })
    result.derived = {"segment": segment, "kpis": kpis}
    return result
