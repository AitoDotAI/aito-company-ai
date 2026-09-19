"""Funnels: the predictive funnel data layer.

A funnel is an ordered set of stages, each a monotone boolean on one table.
For any slice the layer reports, all from Aito:

  - stage counts and step conversion  -> _query totals (descriptive; Python
    only divides counts into percentages, which is formatting, not inference)
  - the calibrated outlook             -> _predict the deepest stage + $why
  - where the slice leaks worst        -> the min-conversion step
  - why it leaks                       -> _relate {$on: [reached_deepest, slice]}
  - the lever that moves it            -> _recommend {goal: reached_deepest}

Two funnels are registered: the inbound website/acquisition funnel over
`sessions`, and the outbound sales funnel over `contacts` (its stage flags
derived from touch history at load time). Same code, two tables. Spec in
docs/09-funnels.md.
"""

from dataclasses import dataclass, field

from . import aitowhy
from .aito import AitoClient


@dataclass
class Stage:
    key: str
    label: str
    flag: str | None  # the monotone boolean; None for the entry stage (all rows)


@dataclass
class FunnelSpec:
    key: str
    label: str
    table: str
    dimensions: list[str]       # sliceable fields, queried directly on the table
    stages: list[Stage]
    cause_fields: list[str]     # pre-event predictors a leak may be attributed to
    lever: str | None           # field _recommend ranks, or None if none is controllable

    @property
    def deepest(self) -> str:
        return self.stages[-1].flag


FUNNELS = {
    "website": FunnelSpec(
        key="website",
        label="Website / acquisition funnel",
        table="sessions",
        dimensions=["source", "campaign", "device", "country", "landing_page"],
        stages=[
            Stage("visitor", "Visitors", None),
            Stage("signup", "Signed up", "signed_up"),
            Stage("trial", "Started trial", "started_trial"),
            Stage("paid", "Converted to paid", "converted_paid"),
        ],
        cause_fields=["source", "campaign", "device", "country", "landing_page"],
        lever="source",
    ),
    "sales": FunnelSpec(
        key="sales",
        label="Sales funnel",
        table="contacts",
        dimensions=["segment", "tier", "ai_lifecycle", "source"],
        stages=[
            Stage("all", "Contacts", None),
            Stage("touched", "Touched", "ever_touched"),
            Stage("reached", "Reached", "ever_reached"),
            Stage("conversation", "Conversation", "ever_conversation"),
            Stage("meeting", "Meeting booked", "ever_meeting"),
        ],
        cause_fields=["segment", "tier", "ai_lifecycle", "source", "country",
                      "role", "notes_tags", "phone_present", "email_present"],
        # `source` (warm / trigger / cold / referral) is the controllable lever:
        # _recommend ranks which acquisition source most reaches the deepest
        # stage (meeting booked), the sales-side counterpart to website's lever.
        lever="source",
    ),
}


@dataclass
class Result:
    calls: list[tuple[str, dict, dict]] = field(default_factory=list)
    derived: dict | None = None


def _slice_where(slice_: dict[str, str]) -> dict:
    return {k: v for k, v in slice_.items() if v}


def _slice_proposition(where: dict) -> dict | None:
    items = [{k: v} for k, v in where.items()]
    if not items:
        return None
    return items[0] if len(items) == 1 else {"$and": items}


def _count(client: AitoClient, result: Result, table: str, where: dict) -> int:
    request = {"from": table, "where": where, "limit": 0}
    response = client.query(request)
    result.calls.append(("_query", request, response))
    return response["total"]


def _outlook(client: AitoClient, result: Result, spec: FunnelSpec, where: dict) -> dict:
    request = {"from": spec.table, "where": where, "predict": spec.deepest,
               "select": ["$p", "$value", "$why"]}
    response = client.predict(request)
    result.calls.append(("_predict", request, response))
    hit = next((h for h in response["hits"] if h["$value"] is True), None)
    if hit is None:
        return {"p": 0.0, "why": []}
    why = [
        {"field": list(f["proposition"])[0],
         "value": aitowhy.prop_value(f["proposition"]),
         "lift": f["value"]}
        for f in aitowhy.lift_factors(hit)
    ]
    return {"p": hit["$p"], "why": sorted(why, key=lambda w: -abs(w["lift"] - 1.0))}


def _causes(client: AitoClient, result: Result, spec: FunnelSpec, where: dict,
            seg_prop: dict | None, top_n: int = 3) -> list[dict]:
    relate = {spec.deepest: True} if seg_prop is None \
        else {"$on": [{spec.deepest: True}, seg_prop]}
    # generous limit: the stage booleans (leaky) consume top slots and are
    # filtered out below, so a small limit can truncate a real cause.
    request = {"from": spec.table, "relate": relate, "limit": 150}
    response = client.relate(request)
    result.calls.append(("_relate", request, response))
    fixed = set(where)
    allowed = set(spec.cause_fields) - fixed
    causes = []
    for hit in response.get("hits", []):
        # v2 relate: goal in `condition`, driver in `related`, `info` a float,
        # frequencies in `fs`.
        related = hit.get("related", {})
        field_name = next(iter(related), None)
        if field_name not in allowed:
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
    causes.sort(key=lambda c: (-c["mi"], c["field"], str(c["value"])))  # deterministic ties
    return causes[:top_n]


def _lever(client: AitoClient, result: Result, spec: FunnelSpec, where: dict) -> dict | None:
    if spec.lever is None or spec.lever in where:
        return None
    request = {"from": spec.table, "where": where, "recommend": spec.lever,
               "goal": {spec.deepest: True}, "limit": 8}
    response = client.recommend(request)
    result.calls.append(("_recommend", request, response))
    options = [{"value": h["$value"], "p": h["$p"]} for h in response.get("hits", [])]
    best, worst = (options[0]["p"], options[-1]["p"]) if options else (0.0, 0.0)
    return {"field": spec.lever, "options": options,
            "lift": (best / worst) if worst else None}


def dimension_values(client: AitoClient, funnel_key: str) -> dict[str, list[str]]:
    """Distinct values per sliceable dimension, read from the data so the
    selectors reflect what is actually loaded (campaigns, countries, etc.)."""
    spec = FUNNELS[funnel_key]
    rows = client.query({"from": spec.table, "limit": 10000})["hits"]
    values: dict[str, set] = {dim: set() for dim in spec.dimensions}
    for row in rows:
        for dim in spec.dimensions:
            v = row.get(dim)
            if v:
                values[dim].add(v)
    return {dim: sorted(vs) for dim, vs in values.items()}


def funnel(client: AitoClient, funnel_key: str, slice_: dict[str, str] | None = None) -> Result:
    assert funnel_key in FUNNELS, f"unknown funnel {funnel_key!r}; have {sorted(FUNNELS)}"
    spec = FUNNELS[funnel_key]
    slice_ = {k: v for k, v in (slice_ or {}).items() if v}
    unknown = set(slice_) - set(spec.dimensions)
    assert not unknown, f"unknown dimensions {sorted(unknown)}; {spec.key} allows {spec.dimensions}"
    where = _slice_where(slice_)
    result = Result()

    # stage counts + step conversion, from Aito _query totals
    stages = []
    prev_count = None
    for stage in spec.stages:
        stage_where = dict(where)
        if stage.flag is not None:
            stage_where[stage.flag] = True
        count = _count(client, result, spec.table, stage_where)
        stages.append({
            "key": stage.key, "label": stage.label, "count": count,
            "rate_of_top": None, "conversion_from_prev": None,
        })
        if prev_count is not None:
            stages[-1]["conversion_from_prev"] = (count / prev_count) if prev_count else None
        prev_count = count
    top = stages[0]["count"]
    for s in stages:
        s["rate_of_top"] = (s["count"] / top) if top else None

    # worst step = the leak
    steps = [s for s in stages if s["conversion_from_prev"] is not None]
    leak = min(steps, key=lambda s: s["conversion_from_prev"]) if steps else None

    seg_prop = _slice_proposition(where)
    result.derived = {
        "funnel": spec.key,
        "label": spec.label,
        "slice": slice_,
        "stages": stages,
        "leak": None if leak is None else {
            "into": leak["label"], "conversion": leak["conversion_from_prev"]},
        "outlook": _outlook(client, result, spec, where),
        "deepest_label": spec.stages[-1].label,
        "causes": _causes(client, result, spec, where, seg_prop),
        "lever": _lever(client, result, spec, where),
    }
    return result
