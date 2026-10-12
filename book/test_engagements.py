"""Engagements (docs/34): the touch row grows into a full engagement.

Proves, on the seed:
  - the import refuses every bad row at once and writes nothing;
  - a good import inserts, re-importing it changes nothing, and an edit is an
    in-place update (idempotent on touch_id, no duplicates);
  - rows arriving out of order renumber the contact's `step`;
  - the contact's funnel flags and the deal's last-touch date follow the
    imported rows (before this, touches logged after a load moved neither);
  - a deal update is an in-place write that records the stage history;
  - the weekly KPIs count it, with null (not 0) for a rate over nothing.
"""

import csv
import json
import tempfile
from datetime import date, datetime
from pathlib import Path

import booktest as bt

from company_ai import engagements, loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _seed(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_touches(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    client.delete_table("deal_events")
    client.create_table("deal_events", loaders.schema.DEAL_EVENTS)


def _tmp(name: str) -> Path:
    return Path(tempfile.mkdtemp(prefix="engagements-")) / name


def _write(path: Path, rows: list[dict]) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=engagements.IMPORT_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in engagements.IMPORT_COLUMNS})
    return path


def _untouched_contact(client: AitoClient) -> dict:
    touched = {t["contact_id"] for t in engagements._all(client, "touches")}
    return sorted((c for c in engagements._all(client, "contacts")
                   if c["contact_id"] not in touched), key=lambda c: c["contact_id"])[0]


def _open_deal(client: AitoClient) -> dict:
    return sorted((d for d in engagements._all(client, "deals") if d.get("won") is None
                   and d["stage"] != "parked"), key=lambda d: d["deal_id"])[0]


def _touches(client: AitoClient, contact_id: str) -> list[str]:
    rows = sorted(engagements._all(client, "touches", {"contact_id": contact_id}),
                  key=lambda r: r["ts"])
    return [f"{r['ts']} {r['touch_id']:10} {r['channel']:8} {r.get('direction') or '-':3} "
            f"step={r.get('step')} hour={r.get('hour')} window={r['window']} "
            f"company={r.get('company_id')} deal={r.get('deal_id')}" for r in rows]


def test_import_refuses_every_bad_row(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed(client)
    contact = _untouched_contact(client)["contact_id"]
    before = client.count("touches")
    base = {"contact_id": contact, "direction": "out", "outcome": "no_reply"}
    path = _write(_tmp("bad.csv"), [
        {**base, "touch_id": "b1", "ts": "2026-09-01T09:00:00", "channel": "email",
         "answered_by": "person"},                                  # a call detail on an email
        {**base, "touch_id": "b2", "ts": "2026-09-01T09:00:00Z", "channel": "email"},  # UTC
        {**base, "touch_id": "b3", "ts": "2026-09-01T10:00:00", "channel": "fax"},
        {**base, "touch_id": "b4", "ts": "2026-09-01T11:00:00", "channel": "email",
         "deal_id": "no-such-deal"},
        {**base, "touch_id": "b5", "ts": "2026-09-01T12:00:00", "channel": "email",
         "hook": "x" * 121},
        {**base, "touch_id": "b6", "ts": "2026-09-01T13:00:00", "channel": "call",
         "outcome": "no_answer", "reply_sentiment": "positive"},
        {**base, "touch_id": "b6", "ts": "2026-09-01T14:00:00", "channel": "sms"},  # dup id
        {**base, "touch_id": "ok", "ts": "2026-09-01T15:00:00", "channel": "sms"},
    ])
    plan = engagements.import_csv(client, path, apply=True)
    t.h1("The report")
    t.tln(engagements.render_plan(plan))
    assert len(plan["problems"]) == 7 and not plan["applied"]
    assert client.count("touches") == before, "a refused import wrote rows"
    t.tln(f"\ntouches before {before}, after {client.count('touches')}: nothing written")


def test_import_is_idempotent_and_resequences(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed(client)
    contact = _untouched_contact(client)
    deal = _open_deal(client)
    cid = contact["contact_id"]
    t.h1("The contact and deal")
    t.tln(f"{cid} {contact['name']} @ {contact['company_id']}; funnel flags: "
          + json.dumps({k: contact[k] for k in engagements.FUNNEL_FLAGS}))
    t.tln(f"{deal['deal_id']} {deal['company']} stage={deal['stage']} "
          f"last_touch_date={deal['last_touch_date']}")

    first = [
        {"touch_id": "e1", "contact_id": cid, "ts": "2026-09-02T08:40:00", "channel": "email",
         "direction": "out", "outcome": "no_reply", "source": "referral", "hook": "peer intro",
         "language": "fi", "gmail_thread_id": "th-1"},
        {"touch_id": "e3", "contact_id": cid, "ts": "2026-09-09T16:20:00", "channel": "call",
         "direction": "out", "outcome": "meeting_booked", "answered_by": "person",
         "deal_id": deal["deal_id"], "next_action": "send agenda",
         "next_action_due": "2026-09-10"},
        {"touch_id": "e4", "contact_id": cid, "ts": "2026-09-16T10:00:00", "channel": "meeting",
         "direction": "out", "outcome": "conversation", "meeting_kind": "first",
         "deal_id": deal["deal_id"], "calendar_event_id": "cal-1"},
    ]
    path = _write(_tmp("first.csv"), first)
    plan = engagements.import_csv(client, path, apply=True)
    t.h1("First import")
    t.tln(engagements.render_plan(plan))
    for line in _touches(client, cid):
        t.tln(line)

    t.h1("The same file again: nothing changes")
    again = engagements.import_csv(client, path, apply=True)
    t.tln(engagements.render_plan(again))
    assert not again["new"] and not again["changed"] and len(again["unchanged"]) == 3

    t.h1("A late row (an earlier reply) and an edited row arrive")
    late = first + [{"touch_id": "e2", "contact_id": cid, "ts": "2026-09-03T12:30:00",
                     "channel": "email", "direction": "in", "outcome": "reply",
                     "reply_sentiment": "positive", "gmail_thread_id": "th-1"},
                    {"touch_id": "e0", "contact_id": cid, "ts": "2026-08-28T09:15:00",
                     "channel": "linkedin", "direction": "out", "outcome": "no_reply",
                     "linkedin_kind": "connect"}]
    late[0] = {**late[0], "outcome": "reply"}       # the first mail did get an answer
    path = _write(_tmp("late.csv"), late)
    plan = engagements.import_csv(client, path, apply=True)
    t.tln(engagements.render_plan(plan))
    lines = _touches(client, cid)
    for line in lines:
        t.tln(line)
    rows = {r["touch_id"]: r for r in engagements._all(client, "touches", {"contact_id": cid})}
    assert len(rows) == 5, "re-import duplicated rows"
    assert [rows[k].get("step") for k in ("e0", "e1", "e3", "e4")] == [1, 2, 3, 4]
    assert rows["e2"].get("step") is None, "an inbound reply took a step"
    assert rows["e1"]["outcome"] == "reply"

    t.h1("The contact's funnel and the deal moved")
    after = engagements._all(client, "contacts", {"contact_id": cid})[0]
    t.tln(json.dumps({k: after[k] for k in engagements.FUNNEL_FLAGS}))
    assert after["ever_meeting"] and after["ever_reached"]
    d = engagements._all(client, "deals", {"deal_id": deal["deal_id"]})[0]
    t.tln(f"{d['deal_id']} last_touch_date {deal['last_touch_date']} -> {d['last_touch_date']}")
    assert d["last_touch_date"] >= "2026-09-16"

    t.h1("Weekly KPIs over it")
    kpis = engagements.weekly(client, as_of=date(2026, 9, 20), weeks=4)
    for w in kpis["weeks"]:
        t.tln(json.dumps(w, sort_keys=True))
    t.tln("open_deals_by_blocker " + json.dumps(kpis["open_deals_by_blocker"]))
    t.tln("lost_by_reason " + json.dumps(kpis["lost_by_reason"]))


def test_log_touch_with_details(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed(client)
    cid = _untouched_contact(client)["contact_id"]
    row = log.log_touch(client, cid, "sms", None, "reply", ts=datetime(2026, 9, 4, 12, 40),
                        direction="in", reply_sentiment="neutral", language="fi")
    t.h1("An inbound SMS, logged with no window")
    t.tln(json.dumps({k: row.get(k) for k in sorted(row) if not k.startswith("search")},
                     sort_keys=True))
    assert row["window"] == "1215" and row["hour"] == 12 and row.get("step") is None
    try:
        log.log_touch(client, cid, "email", None, "no_reply", answered_by="person")
    except AssertionError as e:
        t.tln(f"\na call detail on an email is refused: {str(e).split(';')[0]}")
    else:
        raise AssertionError("answered_by on an email was accepted")


def test_deal_update_is_in_place_and_keeps_history(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed(client)
    deal = _open_deal(client)
    n = client.count("deals")
    log.log_deal_update(client, deal["deal_id"], blocker="gone_silent", as_of=date(2026, 9, 20))
    log.log_deal_update(client, deal["deal_id"], stage="closed_lost", lost_reason="no_decider",
                        as_of=date(2026, 9, 27))
    t.h1("The deal")
    d = engagements._all(client, "deals", {"deal_id": deal["deal_id"]})[0]
    t.tln(json.dumps({k: d.get(k) for k in ("deal_id", "stage", "blocker", "lost_reason",
                                            "won", "last_touch_date")}, sort_keys=True))
    assert client.count("deals") == n, "the update changed the number of deals"
    t.h1("Its stage history")
    for e in sorted(engagements._all(client, "deal_events", {"deal_id": deal["deal_id"]}),
                    key=lambda e: e["date"]):
        t.tln(f"{e['date']} {e.get('prev_stage')} -> {e['stage']} blocker={e['blocker']}")
    try:
        log.log_deal_update(client, _open_deal(client)["deal_id"], lost_reason="price")
    except AssertionError as e:
        t.tln(f"\nrefused: {e}")
