"""The messaging-formula post scorer.

Given a draft's features, predict whether it will win on its channel and
explain which levers move that prediction — the dogfood moment from
operator-ground-truth.md §3. All from Aito:

  - P(win)      -> _predict `won` GIVEN the draft features (per channel)
  - why         -> the $why per-feature contribution on that prediction
  - the levers  -> _recommend the best value of each doctrine lever
                   (tone, link_placement, format, weekday, ai_made)

The success metric is encoded in how `won` is defined per channel (reach
for LinkedIn, views for HN — never upvotes; see schema.py / the loader),
so the scorer optimizes the right thing by construction. Python assembles
requests and orders Aito's returned numbers; it computes no score itself.
"""

from dataclasses import dataclass, field

from . import aitowhy, history
from .aito import AitoClient

# the draft features the scorer conditions on (besides channel)
FEATURES = ["tone", "ai_made", "format", "link_placement", "lane", "topic",
            "length_bucket", "weekday"]
# the actionable writing/mechanics levers the scorer recommends. Deliberately
# excludes `format` (channel-defining, not a lever) and `weekday` (too noisy
# at this data size). Each lever's options are filtered to values that
# actually occur on the chosen channel, so it never suggests an impossible
# combination (e.g. a first-comment link on Hacker News).
LEVERS = ["tone", "link_placement", "ai_made"]


@dataclass
class Result:
    calls: list[tuple[str, dict, dict]] = field(default_factory=list)
    derived: dict | None = None


def _proposition_label(prop: dict) -> str:
    """Render an Aito $why proposition as a label. Handles a single
    `{field: {$has: value}}` and a compound `{$and: [...]}` (joint lift)."""
    (key,) = prop.keys()
    if key == "$and":
        return " & ".join(_proposition_label(p) for p in prop[key])
    inner = prop[key]
    value = inner.get("$has") if isinstance(inner, dict) else inner
    return f"{key}={value}"


def _p_won(client: AitoClient, result: Result, where: dict, with_why: bool) -> dict:
    # learned from measured posts only (history.finished): an unmeasured post's
    # `won` is no outcome. None, not 0.0, when nothing has been measured yet.
    request = {"from": history.finished("posts"), "where": where, "predict": "won",
               "select": ["$p", "$value", "$why"] if with_why else ["$p", "$value"]}
    response = history.predict(client, request)
    if response is None:
        return {"p": None, "why": []}
    result.calls.append(("_predict", request, response))
    hit = next((h for h in response["hits"] if h["$value"] is True), None)
    if hit is None:
        return {"p": None, "why": []}
    why = [
        {"label": _proposition_label(f["proposition"]), "lift": f["value"]}
        for f in aitowhy.lift_factors(hit)
    ]
    return {"p": hit["$p"], "why": sorted(why, key=lambda w: -abs(w["lift"] - 1.0))}


def _feasible_values(client: AitoClient, result: Result, platform: str) -> dict[str, set]:
    """The values of each lever that actually occur on this platform, so the
    recommender can't suggest an off-platform combination."""
    request = {"from": "posts", "where": {"platform": platform}, "limit": 5000}
    response = client.query(request)
    result.calls.append(("_query", request, response))
    feasible: dict[str, set] = {lever: set() for lever in LEVERS}
    for row in response["hits"]:
        for lever in LEVERS:
            if row.get(lever):
                feasible[lever].add(row[lever])
    return feasible


def _lever(client: AitoClient, result: Result, lever: str, where: dict,
           feasible: set) -> dict:
    request = {"from": history.finished("posts"), "where": where, "recommend": lever,
               "goal": {"won": True}, "limit": 8}
    response = history.recommend(client, request)
    if response is None:
        return {"field": lever, "options": []}
    result.calls.append(("_recommend", request, response))
    options = [{"value": h["$value"], "p": h["$p"]}
               for h in response.get("hits", []) if h["$value"] in feasible]
    return {"field": lever, "options": options}


def score(client: AitoClient, platform: str, features: dict[str, str] | None = None) -> Result:
    """Score a draft for a `platform` (linkedin/hackernews/reddit/blog). Any of
    FEATURES may be given; omitted ones are simply not conditioned on."""
    from . import schema
    assert platform in schema.PLATFORMS, \
        f"unknown platform {platform!r}; have {sorted(schema.PLATFORMS)}"
    features = {k: v for k, v in (features or {}).items() if v}
    unknown = set(features) - set(FEATURES)
    assert not unknown, f"unknown features {sorted(unknown)}; allowed {FEATURES}"
    result = Result()

    where = {"platform": platform, **features}
    draft = _p_won(client, result, where, with_why=True)
    base = _p_won(client, result, {"platform": platform}, with_why=False)
    feasible = _feasible_values(client, result, platform)

    levers = []
    for lever in LEVERS:
        # recommend a lever against the other fixed features (drop the lever itself)
        ctx = {k: v for k, v in where.items() if k != lever}
        lv = _lever(client, result, lever, ctx, feasible[lever])
        if not lv["options"]:
            continue
        best = max(lv["options"], key=lambda o: o["p"])
        current = features.get(lever)
        lv["best"] = best["value"]
        lv["current"] = current
        # surface only levers where the best beats the current choice
        lv["actionable"] = current is not None and best["value"] != current
        levers.append(lv)

    result.derived = {
        "platform": platform,
        "features": features,
        "p_win": draft["p"],
        "base_p_win": base["p"],
        "why": draft["why"],
        "levers": levers,
    }
    return result
