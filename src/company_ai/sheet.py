"""One account's sheet, and two lists across accounts (docs/43 §7).

The CRO starts from an account. Its sheet is the account's facts grouped by
kind and slot, read through the ledger so each carries its status, with
superseded facts collapsed under the fact that replaced them; the latest
touch and the unanswered streak; and the derived customer status, direct
deals only. Across accounts: the overdue commitments we owe, and the accounts
whose unanswered streak says stop chasing.

Lookups, counts and dates only, nothing ranked or predicted (rule 2).
Surprising data raises with its row (rule 3); a touch that records no
direction stops the streak and is reported, never skipped.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import clock, facts, schema
from .aito import AitoClient

# an answer, whatever the touch's recorded direction (§7c): a meeting we hosted
# may be logged `out`, and a decline ends the chase by another route
ANSWERS = frozenset({"conversation", "meeting_booked", "reply", "callback_requested", "declined"})
assert ANSWERS <= schema.OUTCOMES
DEFAULT_STREAK = 3
HELSINKI = ZoneInfo("Europe/Helsinki")
DIRECT_ONLY = "direct deals only; indirect relationships are not shown yet"
READ_LIMIT = facts.READ_LIMIT


def helsinki_today() -> date:
    """The day overdue is measured against: the configured as-of date, else
    today in Europe/Helsinki, whatever zone the server runs in (§7b)."""
    return clock.reckoning() or datetime.now(HELSINKI).date()


def unanswered_streak(touches: list[dict]) -> dict:
    """The run of unanswered `out` touches, newest first (§7c). It ends at an
    `in` touch or an answer outcome, either way {streak, ended_by}; or at a
    touch with no recorded direction, which says the count is unknown before
    that touch's date rather than skipping it."""
    ordered = sorted(touches, key=lambda x: (x["ts"], x["touch_id"]), reverse=True)
    streak = 0
    for x in ordered:
        if x["outcome"] not in schema.OUTCOMES:
            raise AssertionError(f"unknown touch outcome; offending row: {x}")
        direction = x.get("direction")
        if x["outcome"] in ANSWERS or direction == "in":
            return {"streak": streak, "ended_by": _ref(x), "unknown_before": None}
        if direction is None:
            return {"streak": streak, "ended_by": None, "unknown_before": x["ts"][:10]}
        if direction != "out":
            raise AssertionError(f"unknown touch direction; offending row: {x}")
        streak += 1
    return {"streak": streak, "ended_by": None, "unknown_before": None}


def _ref(x: dict) -> dict:
    return {"kind": "touch", "id": x["touch_id"], "date": x["ts"][:10], "channel": x["channel"],
            "direction": x.get("direction"), "outcome": x["outcome"]}


def _whole(response: dict, table: str) -> list[dict]:
    facts._whole(response, table, READ_LIMIT)
    return response["hits"]


def _account_touches(client: AitoClient, cid: str, query) -> list[dict]:
    contacts = _whole(query({"from": "contacts", "where": {"company_id": cid},
                             "select": ["contact_id"], "limit": READ_LIMIT}), "contacts")
    who = [{"company_id": cid}, *({"contact_id": c["contact_id"]} for c in contacts)]
    return _whole(query({"from": "touches", "where": {"$or": who}, "limit": READ_LIMIT}), "touches")


def _status(client: AitoClient, cid: str, query) -> dict:
    """Derived customer status, direct only (§7a): a deal whose stage is
    closed_won makes a customer, citing it; otherwise there is no won deal on
    record, never "not a customer"."""
    deals = _whole(query({"from": "deals", "where": {"company_id": cid},
                          "select": ["deal_id", "stage"], "limit": READ_LIMIT}), "deals")
    for d in deals:
        if d["stage"] not in schema.DEAL_STAGES:
            raise AssertionError(f"unknown deal stage; offending row: {d}")
    won = sorted(d["deal_id"] for d in deals if d["stage"] == "closed_won")
    return {"status": "customer" if won else "no won deal on record",
            "sources": [{"kind": "deal", "id": k} for k in won], "qualifier": DIRECT_ONLY}


def account_sheet(client: AitoClient, company: str) -> dict:
    """One account's sheet (§7a): its facts by kind and slot through the
    ledger, superseded ones under their successor; the latest touch and the
    unanswered streak; and the derived customer status. A fact older than the
    latest touch carries "touched since <date>", a pointer that never changes
    its status."""
    requests: list[dict] = []

    def query(request: dict) -> dict:
        requests.append(request)
        return client.query(request)

    cid = facts._company_id(client, company)
    led = facts.ledger(client, company=cid)
    requests.extend(led["requests"])
    # the derived customer row is the sheet's own status line, not a slot
    led["facts"] = [r for r in led["facts"] if r["kind"] != facts.DERIVED_KIND]
    touches = _account_touches(client, cid, query)
    latest = max(touches, key=lambda x: (x["ts"], x["touch_id"])) if touches else None
    touched = latest["ts"][:10] if latest else None

    by_id = {r["fact_id"]: r for r in led["facts"]}
    for r in led["facts"]:
        if r.get("superseded_by") and r["superseded_by"] not in by_id:
            raise AssertionError(f"superseded by a fact this account doesn't have; offending row: {r}")

    def earlier(fact_id: str) -> list[dict]:
        out = []
        for r in led["facts"]:
            if r.get("superseded_by") == fact_id:
                out += [_row(r, None), *earlier(r["fact_id"])]
        return sorted(out, key=lambda r: (r["valid_from"], r["fact_id"]), reverse=True)

    groups: dict[tuple[str, str | None], list[dict]] = {}
    for r in led["facts"]:          # the ledger's order: newest first
        if r["status"] == "superseded":
            continue
        row = _row(r, touched)
        row["earlier"] = earlier(r["fact_id"])
        groups.setdefault((r["kind"], r.get("slot")), []).append(row)
    kinds = sorted(schema.FACT_KINDS)
    ordered = sorted(groups.items(), key=lambda kv: (kinds.index(kv[0][0]), kv[0][1] or ""))
    return {
        "company_id": cid,
        "customer": _status(client, cid, query),
        "latest_touch": _ref(latest) if latest else None,
        "unanswered": unanswered_streak(touches),
        "groups": [{"kind": k, "slot": s, "facts": rows} for (k, s), rows in ordered],
        "requests": requests,
    }


def _row(r: dict, touched: str | None) -> dict:
    return {"fact_id": r["fact_id"], "statement": r["statement"], "kind": r["kind"],
            "slot": r.get("slot"), "state": r.get("state"), "due": r.get("due"),
            "valid_from": r["valid_from"], "author": r["author"], "source": r["source"],
            "status": r["status"],
            "touched_since": (f"touched since {touched}"
                              if touched and r["valid_from"] < touched else None)}


def overdue_commitments(client: AitoClient, today: date | None = None) -> dict:
    """The commitments we owe that are past due (§7b): current `commitment/ours`
    facts not yet sent whose `due` is before today in Helsinki, oldest due first. A due date
    that isn't one raises with its row."""
    today = today or helsinki_today()
    led = facts.ledger(client, kind="commitment", slot="ours")
    out = []
    for r in led["facts"]:
        # a sent commitment is delivered: past its due it isn't owed any more
        if r["status"] == "superseded" or r.get("state") == "sent" or not r.get("due"):
            continue
        try:
            due = date.fromisoformat(r["due"])
        except ValueError:
            raise AssertionError(f"a commitment's due is not a date; offending row: {r}") from None
        if due < today:
            out.append({**_row(r, None), "company_id": r["company_id"], "company": r["company"],
                        "days_overdue": (today - due).days})
    out.sort(key=lambda r: (r["due"], r["fact_id"]))
    return {"today": today.isoformat(), "commitments": out, "count": len(out),
            "requests": led["requests"]}


def unanswered_accounts(client: AitoClient, min_streak: int = DEFAULT_STREAK) -> dict:
    """The stop-chasing list (§7b): accounts whose unanswered streak is at least
    `min_streak`, longest first. A touch belongs to its own company_id, else
    to its contact's company, as on the sheet; touches with neither are
    counted and reported, not dropped."""
    if min_streak < 1:
        raise AssertionError(f"min_streak must be at least 1, got {min_streak}")
    requests = [{"from": "touches", "limit": READ_LIMIT},
                {"from": "contacts", "select": ["contact_id", "company_id"], "limit": READ_LIMIT}]
    touches = _whole(client.query(requests[0]), "touches")
    company_of = {c["contact_id"]: c.get("company_id")
                  for c in _whole(client.query(requests[1]), "contacts")}
    by_account: dict[str, list[dict]] = {}
    orphans = 0
    for x in touches:
        cid = x.get("company_id") or company_of.get(x.get("contact_id"))
        if cid:
            by_account.setdefault(cid, []).append(x)
        else:
            orphans += 1
    out = []
    for cid, rows in by_account.items():
        s = unanswered_streak(rows)
        if s["streak"] >= min_streak:
            last = max(rows, key=lambda x: (x["ts"], x["touch_id"]))
            out.append({"company_id": cid, **s, "latest_touch": _ref(last)})
    out.sort(key=lambda r: (-r["streak"], r["company_id"]))
    return {"min_streak": min_streak, "accounts": out, "count": len(out),
            "touches_without_account": orphans, "requests": requests}
