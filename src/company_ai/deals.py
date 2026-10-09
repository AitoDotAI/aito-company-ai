"""The sales pipeline: weighted value, and Aito's close-likelihood per deal.

Two kinds of output:
  - pipeline aggregates (weighted value = Σ value×probability, open count,
    highest-stakes deal) — deterministic arithmetic over the open deals,
    which is formatting, not inference.
  - close-likelihood + risk per open deal — `_predict won GIVEN stage,
    value_bucket, blocker, champion_present, days_since_touch` over the
    closed-deal history, with the $why. This is the predictive layer: which
    open deals are at risk and why.

The operator's own `probability` is shown alongside Aito's `p_win` so the
two can be compared — where they diverge is the interesting signal.
"""

from dataclasses import dataclass, field
from datetime import date

from . import clock
from . import aitowhy, history, schema
from .aito import AitoClient

STALL_DAYS = 14  # no touch in this many days flags a stalled deal
# Fewer closed deals than this share a feature's value, and its lift is a guess:
# the feature is left out of the evidence, and the answer says so (`thin`).
MIN_PROFILE_EVIDENCE = 8


def _as_bool(value) -> bool:
    """champion_present as the Boolean the column holds. The dashboard sends it
    through a query string ('true'/'false'); a string in a Boolean where-clause
    matches nothing, and Aito silently drops evidence it cannot match, so every
    profile read the same number (the 45% of td-20260928211407945642)."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    assert text in ("true", "false"), f"champion_present must be true/false, got {value!r}"
    return text == "true"


@dataclass
class Result:
    calls: list[tuple[str, dict, dict]] = field(default_factory=list)
    derived: dict | None = None


def _fetch_open(client: AitoClient, result: Result) -> list[dict]:
    # Open = the deal's STAGE is an open stage. (v1 keyed off `won IS NULL`, but
    # v2 coerces a nullable Boolean's null to False — docs/24 — so an open deal
    # would read won=False and look closed-lost. Stage is the source of truth;
    # DEAL_OPEN_STAGES already excludes closed_* and parked.)
    request = {"from": "deals",
               "where": {"stage": {"$or": sorted(schema.DEAL_OPEN_STAGES)}}, "limit": 1000}
    response = client.query(request)
    result.calls.append(("_query", request, response))
    return response["hits"]


def close_likelihood(client: AitoClient, stage: str, blocker: str,
                     champion_present, result: Result | None = None,
                     segment: str | None = None) -> dict:
    """Aito's P(won) + $why for a deal's profile (blocker, champion, and its
    segment when given), learned from CLOSED deals. Keyed on the profile, it is
    the unit the dashboard resolves lazily and caches (one HTTP call per
    profile, GET /api/pwin).

    `stage` is NOT evidence, deliberately: a closed deal's stage is
    closed_won/closed_lost, so no closed row carries an open stage and the
    history holds nothing about how, say, a pilot converts. Putting it in the
    where only looked like conditioning: Aito dropped it, and deals at five
    stages read one number. Stage-aware odds need the stage a deal closed from,
    which the pipeline does not record (see the ticket's follow-up).

    Each feature is evidence when at least MIN_PROFILE_EVIDENCE closed deals
    share its value; Aito combines the features, so the deal needs no exact
    look-alikes (on the seed, 37 of 40 open deals have fewer than 8 closed
    deals matching all three). A thinner value is listed in `thin` with its
    count and left out. Returns `evidence` (the features used), `thin`, `n`
    (closed deals sharing the whole evidence profile) and `basis`: 'profile'
    (every feature used), 'partial' (some thin), 'base_rate' (none: the win
    rate over all closed deals), or 'no_history' when no deal has closed yet
    (no `p_win` at all).

    The history is a nested `from` over closed deals (history.finished): an
    open deal never trains the model, even one whose `won` reads False."""
    features = {"blocker": blocker, "champion_present": _as_bool(champion_present)}
    if segment is not None:
        features["segment"] = segment
    evidence, thin = {}, []
    for feature, value in features.items():
        count_request, count = history.count(client, "deals", {feature: value})
        if result is not None:
            result.calls.append(("_query", count_request, count))
        support = int(count.get("total", 0))
        if support >= MIN_PROFILE_EVIDENCE:
            evidence[feature] = value
        else:
            thin.append({"feature": feature, "value": value, "n": support})
    n = 0
    if evidence:
        count_request, count = history.count(client, "deals", evidence)
        if result is not None:
            result.calls.append(("_query", count_request, count))
        n = int(count.get("total", 0))
    basis = ("base_rate" if not evidence else "partial" if thin else "profile")
    request = {"from": history.finished("deals"), "predict": "won",
               "select": ["$p", "$value", "$why"]}
    if evidence:
        request["where"] = evidence
    response = history.predict(client, request)
    if response is None:
        return {"p_win": None, "why": [], "n": 0, "basis": history.NO_HISTORY,
                "evidence": [], "thin": []}
    if result is not None:
        result.calls.append(("_predict", request, response))
    hit = next((h for h in response["hits"] if h["$value"] is True), None)
    out = {"n": n, "basis": basis, "evidence": sorted(evidence), "thin": thin}
    if hit is None:
        return {"p_win": None, "why": [], **out}
    why = [{"label": _why_label(f["proposition"]), "lift": f["value"]}
           for f in aitowhy.lift_factors(hit)]
    why.sort(key=lambda w: -abs(w["lift"] - 1.0))
    return {"p_win": hit["$p"], "why": why, **out}


def _close_likelihood(client: AitoClient, result: Result, deal: dict, as_of: date) -> dict:
    days = (as_of - date.fromisoformat(deal["last_touch_date"])).days
    cl = close_likelihood(client, deal["stage"], deal["blocker"],
                          deal["champion_present"], result, segment=deal["segment"])
    return {"p_win": cl["p_win"], "why": cl["why"], "n": cl["n"], "basis": cl["basis"],
            "thin": cl["thin"], "days_since_touch": days}


def _why_label(prop: dict) -> str:
    (key,) = prop.keys()
    if key == "$and":
        return " & ".join(_why_label(p) for p in prop[key])
    inner = prop[key]
    if isinstance(inner, dict) and "$exists" in inner:
        # A reverse-link proposition ($refs ... $exists) carries no plain value,
        # so the generic `key=value` rendered it as "...company_id=None". Name
        # what the set was filtered on instead — that is the fact a reader is
        # being told moved the number.
        filt = inner["$exists"]
        if isinstance(filt, dict) and filt:
            return f"{key} has " + ", ".join(f"{k}={v}" for k, v in sorted(filt.items()))
        return f"{key} exists"
    value = inner.get("$has") if isinstance(inner, dict) else inner
    return f"{key}={value}"


def _by_p_win(deal: dict) -> tuple:
    """highest P(won) first; deals with no P(won) (no closed history) last"""
    return (deal["p_win"] is None, -(deal["p_win"] or 0.0))


def who_to_reach(client: AitoClient, as_of: date | None = None, top_n: int = 10,
                 predict: bool = True) -> Result:
    """The marquee entity-graph query (.ai/tasks/15): the contacts to reach at
    companies with a STALLED deal, the stalled deals ranked by Aito's
    close-likelihood. A high-`p_win` deal gone quiet is the priority to unstick;
    its people are found in ONE relational pass over the `company_id` link
    (`contacts.company_id → companies`), not a hand-joined string match — the
    difference the entity graph buys. Prediction stays Aito's (the pipeline's
    `_predict` close-likelihood); Python only groups the link results (rule 2).

    `predict=False` returns the stalled deals + their people WITHOUT the
    close-likelihood (ordered by how long they've been quiet), so the route is
    instant; the dashboard fills p_win in lazily via the shared /api/pwin cache
    and ranks client-side. predict=True (default) ranks server-side by p_win —
    the MCP tool and booktest path, unchanged."""
    from .loaders import company_slug
    result = Result()
    pipe = pipeline(client, as_of, predict=predict)
    result.calls.extend(pipe.calls)
    stalled = [d for d in pipe.derived["deals"] if d["stalled"]]
    stalled = (sorted(stalled, key=_by_p_win)[:top_n] if predict
               else sorted(stalled, key=lambda d: -d["days_since_touch"]))
    by_slug = {company_slug(d["company"]): d for d in stalled}
    contacts: list[dict] = []
    if by_slug:
        request = {"from": "contacts", "where": {"company_id": {"$or": list(by_slug)}},
                   "select": ["contact_id", "name", "role", "company_id"], "limit": 10000}
        response = client.query(request)
        result.calls.append(("_query", request, response))
        contacts = response["hits"]
    ordered = (sorted(by_slug.items(), key=lambda kv: _by_p_win(kv[1])) if predict
               else sorted(by_slug.items(), key=lambda kv: -kv[1]["days_since_touch"]))
    rows = []
    for slug, d in ordered:
        people = [{"contact_id": c["contact_id"], "name": c["name"], "role": c.get("role")}
                  for c in contacts if c.get("company_id") == slug]
        rows.append({"company": d["company"], "deal_id": d["deal_id"], "stage": d["stage"],
                     "segment": d["segment"],
                     "blocker": d["blocker"], "champion_present": d["champion_present"],
                     "p_win": d["p_win"], "n": d["n"], "basis": d["basis"], "thin": d["thin"],
                     "days_since_touch": d["days_since_touch"],
                     "contacts": people})
    result.derived = {"as_of": pipe.derived["as_of"], "count": len(rows), "rows": rows}
    return result


def pipeline(client: AitoClient, as_of: date | None = None, predict: bool = True) -> Result:
    """The open pipeline ranked by weighted value, each deal with Aito's
    close-likelihood, a risk flag, and a stalled flag.

    `predict=False` skips the per-deal `_predict` (p_win/why stay None) and
    returns instantly — the aggregates and the stalled flag are pure arithmetic
    over the operator's own probability and touch dates. The dashboard uses it
    to paint the pipeline immediately, then fills each deal's close-likelihood
    in lazily via `close_likelihood` (GET /api/pwin)."""
    as_of = as_of or clock.today()
    result = Result()
    deals = _fetch_open(client, result)

    ranked = []
    for d in deals:
        days = (as_of - date.fromisoformat(d["last_touch_date"])).days
        weighted = d["value_eur"] * d["probability"] / 100.0
        row = {
            "deal_id": d["deal_id"], "company": d["company"], "segment": d["segment"],
            "stage": d["stage"], "value_eur": d["value_eur"],
            "probability": d["probability"], "weighted_value": round(weighted),
            "champion_present": d["champion_present"], "blocker": d["blocker"],
            "days_since_touch": days, "stalled": days > STALL_DAYS,
            "p_win": None, "why": [], "n": None, "basis": None, "thin": [],
        }
        if predict:
            cl = _close_likelihood(client, result, d, as_of)
            row["p_win"], row["why"] = cl["p_win"], cl["why"][:3]
            row["n"], row["basis"], row["thin"] = cl["n"], cl["basis"], cl["thin"]
        ranked.append(row)
    ranked.sort(key=lambda d: -d["weighted_value"])

    open_value = sum(d["value_eur"] for d in ranked)
    weighted_total = sum(d["weighted_value"] for d in ranked)
    result.derived = {
        "as_of": as_of.isoformat(),
        "kpis": {
            "weighted_pipeline": weighted_total,
            "open_value": open_value,
            "open_deals": len(ranked),
            "stalled": sum(1 for d in ranked if d["stalled"]),
        },
        "deals": ranked,
    }
    return result
