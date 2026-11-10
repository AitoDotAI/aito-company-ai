"""The account sheet and the two lists across accounts (docs/43 §7,
td-20261110230516558720). The CRO starts from an account: its facts by slot
with their status, superseded ones collapsed, a "touched since" pointer that
never changes status, the latest touch and the unanswered streak, and the
derived customer status with its direct-only qualifier. Across accounts: the
commitments we owe that are overdue, and the accounts to stop chasing.
Lookups, counts and dates only (rule 2). Requires a running Aito instance."""

import re
from datetime import date, datetime

import booktest as bt

from book._target import guarded_client
from company_ai import loaders, log, sheet
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR

SEED = loaders._read_csv(SEED_DIR / "facts.csv")
REPLICA = SEED[0]["company"]
RID = loaders.company_slug(REPLICA)
REPLICA_CONTACT = "sc016"
QUIET, QUIET_CONTACT = "Strickland GmbH", "sc043"
WON = "Delos Ab"


def _seeded() -> AitoClient:
    client = guarded_client()   # refuses anything but a test env, before any call
    client.delete_table("changelog")
    loaders.create_schema(client)
    loaders.load_all(client, SEED_DIR)
    return client


def _touch(client, contact, day, direction, outcome, channel="email"):
    kwargs = {"direction": direction} if direction else {}
    log.log_touch(client, contact, channel, None, outcome,
                  ts=datetime.fromisoformat(f"{day}T10:00:00"), **kwargs)


def _id(x: str) -> str:
    return re.sub(r"(fa|to|st)-?\d{14,20}", r"\1-new", x)


def _show_sheet(t: bt.TestCaseRun, s: dict) -> None:
    c = s["customer"]
    t.tln(f"  customer: {c['status']} {[x['id'] for x in c['sources']]} ({c['qualifier']})")
    lt = s["latest_touch"]
    t.tln(f"  latest touch: {lt and (lt['date'], lt['channel'], lt['direction'], lt['outcome'])}")
    u = s["unanswered"]
    t.tln(f"  unanswered: {u['streak']}, ended by "
          f"{u['ended_by'] and (u['ended_by']['date'], u['ended_by']['outcome'])}, "
          f"unknown before {u['unknown_before']}")
    for g in s["groups"]:
        t.tln(f"  {g['kind']}{'/' + g['slot'] if g['slot'] else ''}:")
        for f in g["facts"]:
            t.tln(f"    {_id(f['fact_id'])} {f['statement']!r} {f['valid_from']} "
                  f"[{f['status']}] {f['touched_since'] or ''}")
            for e in f["earlier"]:
                t.tln(f"      earlier: {_id(e['fact_id'])} {e['statement']!r} [{e['status']}]")
    t.tln(f"  requests: {[(r.get('from'), sorted((r.get('where') or {}).keys())) for r in s['requests']]}")


def test_the_streak_rule(t: bt.TestCaseRun) -> None:
    def row(i, direction, outcome):
        return {"touch_id": f"t{i}", "ts": f"2026-11-0{i}T10:00:00", "channel": "email",
                "direction": direction, "outcome": outcome}
    cases = {
        "three outs after an in": [row(1, "in", "reply"), *(row(i, "out", "no_reply") for i in (2, 3, 4))],
        "a decline ends it": [row(1, "out", "no_reply"), row(2, "out", "declined"), row(3, "out", "no_reply")],
        "an out meeting is an answer": [row(1, "out", "no_reply"), row(2, "out", "meeting_booked"),
                                        row(3, "out", "no_reply"), row(4, "out", "no_answer")],
        "a held conversation logged out": [row(1, "out", "conversation"), row(2, "out", "no_answer")],
        "a bounce is not an answer": [row(1, "in", "reply"), row(2, "out", "bounced"), row(3, "out", "no_reply")],
        "no direction stops it": [row(1, "out", "no_reply"), row(2, None, "no_answer"), row(3, "out", "no_reply")],
        "no touches": [],
    }
    want = {"three outs after an in": (3, None), "a decline ends it": (1, None),
            "an out meeting is an answer": (2, None), "a held conversation logged out": (1, None),
            "a bounce is not an answer": (2, None), "no direction stops it": (1, "2026-11-02"),
            "no touches": (0, None)}
    t.h1("unanswered_streak, newest first")
    for name, rows in cases.items():
        s = sheet.unanswered_streak(rows)
        t.tln(f"  {name}: {s['streak']} (ended by {s['ended_by'] and s['ended_by']['outcome']}, "
              f"unknown before {s['unknown_before']})")
        assert (s["streak"], s["unknown_before"]) == want[name], (name, s)
    try:
        sheet.unanswered_streak([row(1, "sideways", "no_reply")])
    except AssertionError as e:
        t.tln(f"  an unknown direction raises: {str(e)[:40]}")
    else:
        raise AssertionError("an unknown direction must raise")


def test_one_account_sheet(t: bt.TestCaseRun) -> None:
    client = _seeded()
    _touch(client, REPLICA_CONTACT, "2026-11-02", "out", "no_reply")
    s = sheet.account_sheet(client, REPLICA)
    t.h1("account_sheet(<replica>), after an out touch on 2026-11-02")
    _show_sheet(t, s)
    assert s["customer"]["status"] == "no won deal on record"
    assert s["customer"]["qualifier"] == "direct deals only; indirect relationships are not shown yet"
    listed = [f for g in s["groups"] for f in g["facts"]]
    collapsed = [e for f in listed for e in f["earlier"]]
    every = {f["fact_id"] for f in SEED if f["company"] == REPLICA}
    assert {f["fact_id"] for f in listed} | {e["fact_id"] for e in collapsed} == every, \
        "every fact is on the sheet, superseded ones collapsed"
    assert all(e["status"] == "superseded" for e in collapsed) and collapsed
    assert all(f["status"] != "superseded" for f in listed)
    older = [f for f in listed if f["valid_from"] < "2026-11-02"]
    assert older and all(f["touched_since"] == "touched since 2026-11-02" for f in older), \
        "the pointer's wording is pinned, never a staleness signal"
    assert all(f["status"] == "active" for f in older), "touched since never changes status"
    assert all(f["touched_since"] is None for f in listed if f["valid_from"] >= "2026-11-02")
    assert s["unanswered"]["streak"] == 1 and s["unanswered"]["unknown_before"], \
        "the seed's touches record no direction, so the count stops there"


def test_a_won_deal_makes_a_customer(t: bt.TestCaseRun) -> None:
    client = _seeded()
    s = sheet.account_sheet(client, WON)
    t.h1("account_sheet(<an account with a won deal>)")
    _show_sheet(t, s)
    assert s["customer"]["status"] == "customer"
    won = sorted(d["deal_id"] for d in loaders._read_csv(SEED_DIR / "deals.csv")
                 if d["company"] == WON and d["stage"] == "closed_won")
    assert won and [x["id"] for x in s["customer"]["sources"]] == won, "every won deal is cited"


def test_overdue_commitments_by_the_helsinki_day(t: bt.TestCaseRun) -> None:
    client = _seeded()
    out = sheet.overdue_commitments(client, today=date(2026, 11, 12))
    t.h1("overdue_commitments(today=2026-11-12)")
    for r in out["commitments"]:
        t.tln(f"  {r['fact_id']} {r['company_id']} due {r['due']} ({r['days_overdue']} days): "
              f"{r['statement']!r}")
    dues = {r["fact_id"]: r["due"] for r in out["commitments"]}
    ours = {f["fact_id"]: f["due"] for f in SEED
            if f["kind"] == "commitment" and f["slot"] == "ours" and not f["superseded_by"] and f["due"]}
    assert dues == {k: v for k, v in ours.items() if v < "2026-11-12"}, (dues, ours)
    assert any(v == "2026-11-12" for v in ours.values()), "the seed has one due that day: not overdue"


def test_the_stop_chasing_list(t: bt.TestCaseRun) -> None:
    client = _seeded()
    _touch(client, QUIET_CONTACT, "2026-11-01", "in", "reply")
    for day in ("2026-11-03", "2026-11-05", "2026-11-07"):
        _touch(client, QUIET_CONTACT, day, "out", "no_reply")
    out = sheet.unanswered_accounts(client)
    t.h1("unanswered_accounts(min_streak=3)")
    for r in out["accounts"]:
        t.tln(f"  {r['company_id']}: {r['streak']} since {r['ended_by'] and r['ended_by']['date']}, "
              f"latest {r['latest_touch']['date']}")
    t.tln(f"  touches naming no account: {out['touches_without_account']}")
    t.tln(f"  requests: {out['requests']}")
    assert [r["company_id"] for r in out["accounts"]] == [loaders.company_slug(QUIET)]
    _touch(client, QUIET_CONTACT, "2026-11-08", "out", "meeting_booked")
    assert sheet.unanswered_accounts(client)["accounts"] == [], "a booked meeting is an answer"
