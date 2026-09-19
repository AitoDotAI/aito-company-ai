"""The three brief queries, as specified in docs/03-morning-brief.md.

Every probability and every ranking comes out of an Aito call; Python
here only assembles spec'd exclusion lists, joins names for display,
and sorts by Aito's own $p. Each function returns a Result that keeps
the raw (request, response) pairs so booktests and `brief --no-llm`
can print exactly what was asked and answered.

Follow-up closure semantics: the schema has no "done" flag, so a
follow-up (a touch carrying next_action_due) counts as OPEN only while
the contact has no later touch; logging any newer touch closes it.
Without this, the follow-up list and the query-1 exclusion "open
next_action not yet due" would be unimplementable.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from . import schema
from .aito import AitoClient

GOOD_OUTCOMES = ["conversation", "meeting_booked", "callback_requested"]
OPENER_OUTCOMES = ["conversation", "meeting_booked"]
RETOUCH_COOLDOWN_DAYS = 5
FOLLOWUP_HORIZON_DAYS = 3  # the 72h email->call rule
CALL_WINDOWS = {"0800", "1215", "1600"}


@dataclass
class Result:
    calls: list[tuple[dict, dict]] = field(default_factory=list)
    derived: dict | list | None = None


def bucket_days_since(days: int | None) -> str:
    """Recency state at the moment of a touch; 'first' = never touched before."""
    if days is None:
        return "first"
    assert days >= 0, f"negative days_since: {days}"
    if days <= 2:
        return "0-2"
    if days <= 7:
        return "3-7"
    if days <= 21:
        return "8-21"
    return "22+"


def _ts_date(touch: dict) -> date:
    return datetime.fromisoformat(touch["ts"]).date()


def _fetch_all(client: AitoClient, result: Result, table: str) -> list[dict]:
    request = {"from": table, "limit": 10000}
    response = client.query(request)
    assert response["total"] <= 10000, f"{table} exceeds fetch limit; raise it"
    result.calls.append((request, response))
    return response["hits"]


def _last_touch_dates(touches: list[dict]) -> dict[str, date]:
    last: dict[str, date] = {}
    for touch in touches:
        day = _ts_date(touch)
        if touch["contact_id"] not in last or day > last[touch["contact_id"]]:
            last[touch["contact_id"]] = day
    return last


def _open_followups(touches: list[dict], last_touch: dict[str, date]) -> list[dict]:
    return [
        t for t in touches
        if t.get("next_action_due") and _ts_date(t) >= last_touch[t["contact_id"]]
    ]


def who_to_call(
    client: AitoClient, window: str, top_n: int = 5, as_of: date | None = None
) -> Result:
    """Query 1: contacts ranked by Aito's $p of a good outcome now."""
    assert window in schema.WINDOWS, f"unknown window {window!r}"
    as_of = as_of or date.today()
    weekday = schema.WEEKDAYS[as_of.weekday()]
    result = Result()
    contacts = _fetch_all(client, result, "contacts")
    touches = _fetch_all(client, result, "touches")
    last_touch = _last_touch_dates(touches)

    # exclusions per docs/03, applied before ranking
    pending = {
        t["contact_id"]
        for t in _open_followups(touches, last_touch)
        if date.fromisoformat(t["next_action_due"]) > as_of
    }
    recently_touched = {
        cid for cid, day in last_touch.items()
        if (as_of - day).days < RETOUCH_COOLDOWN_DAYS
    }
    eligible = [
        c for c in contacts
        if c["contact_id"] not in pending
        and c["contact_id"] not in recently_touched
        and (c["phone_present"] or window not in CALL_WINDOWS)
    ]

    ranked = []
    for contact in eligible:
        days = (as_of - last_touch[contact["contact_id"]]).days \
            if contact["contact_id"] in last_touch else None
        request = {
            "from": "touches",
            "where": {
                "window": window,
                "weekday": weekday,
                "contact_id.segment": contact["segment"],
                "contact_id.tier": contact["tier"],
                "contact_id.ai_lifecycle": contact["ai_lifecycle"],
                "days_since_prev_touch": bucket_days_since(days),
            },
            "predict": "outcome",
            "limit": len(schema.OUTCOMES),
        }
        response = client.predict(request)
        # outcome features are mutually exclusive, so the spec's
        # $p(outcome in GOOD_OUTCOMES) is the sum of Aito's per-outcome $p
        p_good = sum(
            hit["$p"] for hit in response["hits"] if hit["$value"] in GOOD_OUTCOMES
        )
        ranked.append((p_good, contact, request, response))

    ranked.sort(key=lambda r: (-r[0], r[1]["contact_id"]))
    top = ranked[:top_n]
    result.calls.extend((req, res) for _, _, req, res in top)
    result.derived = [
        {
            "contact_id": c["contact_id"],
            "name": c["name"],
            "company": c["company"],
            "phone_present": c["phone_present"],
            "$p": p,
            "why": {k.removeprefix("contact_id."): v for k, v in top_req["where"].items()},
        }
        for p, c, top_req, _ in top
    ]
    return result


def opener_context(client: AitoClient, contact_id: str, top_n: int = 3) -> Result:
    """Query 2: evidence touches from statistically similar contacts."""
    result = Result()
    request = {"from": "contacts", "where": {"contact_id": contact_id}, "limit": 1}
    response = client.query(request)
    result.calls.append((request, response))
    assert response["hits"], f"unknown contact_id {contact_id!r}"
    contact = response["hits"][0]

    # evidence pool: anyone else's touches that ended well (retrieval only)
    pool_request = {
        "from": "touches",
        "where": {
            "outcome": {"$or": OPENER_OUTCOMES},
            "contact_id": {"$not": contact_id},
        },
        "limit": 1000,
    }
    pool = client.query(pool_request)
    result.calls.append((pool_request, pool))

    by_contact: dict[str, dict] = {}
    for touch in sorted(pool["hits"], key=lambda t: t["ts"]):
        by_contact[touch["contact_id"]] = touch  # keeps each contact's latest

    if not by_contact:
        result.derived = []
        return result

    # v2 dropped the feature `_similarity` endpoint and has no feature-similarity
    # query ($nn/$knn are vector-only) — docs/24. Keep the retrieval Aito-side:
    # evidence from contacts that SHARE the target's segment (the primary
    # conditioning feature, docs/03 query 2), most recent first. Graded
    # three-feature similarity isn't expressible on v2; this is the honest filter.
    match_request = {
        "from": "contacts",
        "where": {"contact_id": {"$or": sorted(by_contact)}, "segment": contact["segment"]},
        "limit": 1000,
        "select": ["contact_id", "name", "company", "segment", "tier", "ai_lifecycle"],
    }
    matched = client.query(match_request)
    result.calls.append((match_request, matched))

    # order by the recency of each contact's evidence touch (formatting, not a
    # predictive ranking — rule 2)
    ordered = sorted(matched["hits"],
                     key=lambda c: by_contact[c["contact_id"]]["ts"], reverse=True)[:top_n]
    result.derived = [
        {
            "similar_contact": c["name"],
            "company": c["company"],
            "segment": c["segment"],
            "tier": c["tier"],
            "ai_lifecycle": c["ai_lifecycle"],
            "evidence": {
                key: by_contact[c["contact_id"]].get(key)
                for key in ("ts", "channel", "window", "outcome", "notes")
            },
        }
        for c in ordered
    ]
    return result


def what_changed(client: AitoClient, as_of: date | None = None) -> Result:
    """Query 3: yesterday's touches plus open follow-ups due within 72h."""
    as_of = as_of or date.today()
    result = Result()

    since = (as_of - timedelta(days=1)).isoformat() + "T00:00:00"
    recent_request = {"from": "touches", "where": {"ts": {"$gte": since}}, "limit": 100}
    recent = client.query(recent_request)
    result.calls.append((recent_request, recent))

    horizon = (as_of + timedelta(days=FOLLOWUP_HORIZON_DAYS)).isoformat()
    due_request = {
        "from": "touches",
        # v2: two operators on one field (a field-level `$and` matched all rows),
        # and `$gt ""` for "is set" — a null String is absent, so this keeps only
        # touches that carry a due date, on or before the horizon (docs/24).
        "where": {"next_action_due": {"$gt": "", "$lte": horizon}},
        "limit": 100,
    }
    due = client.query(due_request)
    result.calls.append((due_request, due))

    touches = _fetch_all(client, Result(), "touches")
    last_touch = _last_touch_dates(touches)
    open_ids = {t["touch_id"] for t in _open_followups(touches, last_touch)}
    names = {c["contact_id"]: c for c in _fetch_all(client, Result(), "contacts")}

    followups = sorted(
        (t for t in due["hits"] if t["touch_id"] in open_ids),
        key=lambda t: (t["next_action_due"], t["touch_id"]),
    )
    result.derived = {
        "since_yesterday": [
            {
                "name": names[t["contact_id"]]["name"],
                "company": names[t["contact_id"]]["company"],
                "ts": t["ts"],
                "channel": t["channel"],
                "outcome": t["outcome"],
                "notes": t.get("notes"),
            }
            for t in sorted(recent["hits"], key=lambda t: t["ts"])
        ],
        "follow_ups_due": [
            {
                "contact_id": t["contact_id"],
                "name": names[t["contact_id"]]["name"],
                "company": names[t["contact_id"]]["company"],
                "next_action": t["next_action"],
                "due": t["next_action_due"],
            }
            for t in followups
        ],
    }
    return result
