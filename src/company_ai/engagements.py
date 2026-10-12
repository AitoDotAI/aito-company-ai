"""Engagements: the sales funnel's raw rows (docs/34).

A touch row is one engagement (an email, call, SMS, LinkedIn touch or meeting,
in or out), linked to its contact, company and, when there is one, its deal.
This module holds what depends on MANY rows at once:

- `resequence` — a contact's outbound `step`, recency bucket and company on
  every one of its touches, and the contact's funnel flags. One new row can
  renumber the rows after it (a backfill arrives out of order), and the funnel
  flags used to be stamped only at load time, so touches logged live never
  moved the sales funnel. Every write that adds touches ends here.
- `import_csv` — the bulk import: idempotent on `touch_id`, every row checked
  and every refusal reported at once, nothing written if any row is refused.
- `weekly` — the KPI view: deterministic counting per ISO week, like
  saleskpi.py. Prediction stays in Aito (rule 2); this is the accounting.
"""

import csv
import datetime as dt
from collections import Counter, defaultdict
from pathlib import Path

from . import changelog, loaders, schema, search
from .aito import AitoClient

# the import's columns, in order (the contract the backfill is written to)
IMPORT_COLUMNS = ["touch_id", "contact_id", "deal_id", "ts", "channel", "direction",
                  "outcome", "answered_by", "linkedin_kind", "meeting_kind",
                  "reply_sentiment", "source", "hook", "template", "language",
                  "gmail_thread_id", "calendar_event_id", "next_action",
                  "next_action_due", "notes"]
# the columns of a touch that resequence derives
SEQUENCE_COLUMNS = ("days_since_prev_touch", "step", "company_id")
FUNNEL_FLAGS = ("ever_touched", "ever_reached", "ever_conversation", "ever_meeting")
# the fields an import may change on a touch it already holds
STORED_COLUMNS = [c for c in IMPORT_COLUMNS if c != "touch_id"] + [
    "weekday", "window", "hour", "good_outcome", "reached", "booked"]
LIMIT = 1_000_000


def _all(client: AitoClient, table: str, where: dict | None = None) -> list[dict]:
    q = {"from": table, "limit": LIMIT}
    if where:
        q["where"] = where
    return client.query(q)["hits"]


def resequence(client: AitoClient, contact_ids: set[str]) -> dict:
    """Re-derive the history-dependent columns for every touch of these
    contacts, and their funnel flags; write only what changed, then read the
    contacts back (rule 3: a write that did not land is an error, not a hope)."""
    if not contact_ids:
        return {"touches_updated": 0, "contacts_updated": 0, "deals_updated": 0}
    contacts = {c["contact_id"]: c for c in _all(client, "contacts")
                if c["contact_id"] in contact_ids}
    missing = contact_ids - set(contacts)
    assert not missing, f"resequence: unknown contact_id(s) {sorted(missing)}"
    touches = [t for t in _all(client, "touches") if t["contact_id"] in contact_ids]
    before = {t["touch_id"]: {c: t.get(c) for c in SEQUENCE_COLUMNS} for t in touches}
    loaders.derive_sequence(touches, {k: c.get("company_id") for k, c in contacts.items()})
    touch_updates = []
    for t in touches:
        change = {c: t.get(c) for c in SEQUENCE_COLUMNS if t.get(c) != before[t["touch_id"]][c]}
        if change:
            touch_updates.append(({"touch_id": t["touch_id"]}, change))
    client.update_many("touches", touch_updates)

    outcomes: dict[str, list[str]] = defaultdict(list)
    for t in touches:
        outcomes[t["contact_id"]].append(t["outcome"])
    contact_updates = []
    for cid, contact in contacts.items():
        flags = schema.contact_funnel_flags(outcomes.get(cid, []))
        change = {k: v for k, v in flags.items() if contact.get(k) != v}
        if change:
            contact_updates.append(({"contact_id": cid}, change))
    client.update_many("contacts", contact_updates)
    if contact_updates:
        after = {c["contact_id"]: c for c in _all(client, "contacts")
                 if c["contact_id"] in contact_ids}
        for where, change in contact_updates:
            got = after[where["contact_id"]]
            wrong = {k: (v, got.get(k)) for k, v in change.items() if got.get(k) != v}
            assert not wrong, f"contact {where['contact_id']}: wrote/read back {wrong}"

    # a touch on a deal is the deal being worked: carry its date to the deal's
    # last_touch_date (forward only), or every deal whose engagements arrive
    # by import reads as stalled
    latest: dict[str, str] = {}
    for t in touches:
        if t.get("deal_id"):
            latest[t["deal_id"]] = max(latest.get(t["deal_id"], ""), t["ts"][:10])
    deal_updates = []
    if latest:
        for d in _all(client, "deals"):
            if d["deal_id"] in latest and latest[d["deal_id"]] > (d.get("last_touch_date") or ""):
                deal_updates.append(({"deal_id": d["deal_id"]},
                                     {"last_touch_date": latest[d["deal_id"]]}))
    client.update_many("deals", deal_updates)
    return {"touches_updated": len(touch_updates), "contacts_updated": len(contact_updates),
            "deals_updated": len(deal_updates)}


def _row_from_import(raw: dict) -> dict:
    """An import row in the shape parse_touch_row checks: the import leaves out
    weekday and window, which are functions of ts, so derive them here; a bad
    ts is left for the parser to report."""
    row = {c: (raw.get(c) or "").strip() for c in IMPORT_COLUMNS}
    try:
        ts = dt.datetime.fromisoformat(row["ts"])
        row["weekday"] = schema.WEEKDAYS[ts.weekday()]
        row["window"] = schema.window_for(ts.hour)
    except ValueError:
        row["weekday"], row["window"] = "?", "other"
    return row


def check_import(client: AitoClient, path: Path) -> dict:
    """Read and check an import file against the instance, collecting every
    problem. Returns the plan: parsed rows split into new / changed /
    unchanged, plus `problems` [(line, message)] and `possible_duplicates`
    (a hand-logged touch on the same contact, channel and day — reported,
    not refused, since two calls in a day are real)."""
    path = Path(path)
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        raws = list(reader)
    problems: list[tuple[int, str]] = []
    if header != IMPORT_COLUMNS:
        problems.append((1, f"header must be exactly: {','.join(IMPORT_COLUMNS)}"
                            f" — got: {','.join(header)}"))
        return {"rows": len(raws), "problems": problems}

    contact_ids = {c["contact_id"] for c in _all(client, "contacts")}
    deal_ids = {d["deal_id"] for d in _all(client, "deals")}
    existing = {t["touch_id"]: t for t in _all(client, "touches")}

    parsed, seen_id, seen_key = [], {}, {}
    for line, raw in enumerate(raws, start=2):
        sink: list[str] = []
        token = loaders._COLLECT.set(sink)
        row = None
        try:
            row = loaders.parse_touch_row(_row_from_import(raw), contact_ids, deal_ids)
        except Exception as e:  # noqa: BLE001 — a cascade after a recorded failure
            if not sink:
                sink.append(str(e).split("; offending row:")[0])
        finally:
            loaders._COLLECT.reset(token)
        tid = (raw.get("touch_id") or "").strip()
        if tid in seen_id:
            sink.append(f"duplicate touch_id {tid!r} (first on line {seen_id[tid]})")
        seen_id.setdefault(tid, line)
        if row is not None and not sink:
            key = (row["contact_id"], row["ts"], row["channel"], row["direction"])
            if key in seen_key:
                sink.append(f"same contact, ts, channel and direction as line {seen_key[key]}"
                            " under another touch_id")
            seen_key.setdefault(key, line)
        problems.extend((line, m) for m in sink)
        if row is not None and not sink:
            parsed.append(row)

    new, changed, unchanged = [], [], []
    for row in parsed:
        old = existing.get(row["touch_id"])
        if old is None:
            new.append(row)
            continue
        if old["contact_id"] != row["contact_id"]:
            problems.append((0, f"touch_id {row['touch_id']!r} already belongs to contact "
                                f"{old['contact_id']!r}, not {row['contact_id']!r}"))
            continue
        diff = {c: row.get(c) for c in STORED_COLUMNS if old.get(c) != row.get(c)}
        (changed if diff else unchanged).append((row, diff))

    hand_logged = defaultdict(list)
    for t in existing.values():
        hand_logged[(t["contact_id"], t["channel"], t["ts"][:10])].append(t["touch_id"])
    possible_duplicates = [
        (row["touch_id"], others) for row in new
        if (others := [o for o in hand_logged[(row["contact_id"], row["channel"], row["ts"][:10])]
                       if o != row["touch_id"]])]
    return {"rows": len(raws), "problems": problems, "new": new, "changed": changed,
            "unchanged": unchanged, "possible_duplicates": possible_duplicates}


def import_csv(client: AitoClient, path: Path, apply: bool = False) -> dict:
    """Check, then (with apply) write: insert new rows, update changed ones in
    place by touch_id, and resequence every contact touched. Nothing is written
    if any row is refused."""
    plan = check_import(client, path)
    plan["applied"] = False
    if plan["problems"] or not apply:
        return plan
    new = [{**r, "days_since_prev_touch": "first", "step": None, "company_id": None}
           for r in plan["new"]]
    for i in range(0, len(new), 200):
        client.upload_batch("touches", new[i:i + 200])
    client.optimize("touches")
    client.update_many("touches", [({"touch_id": r["touch_id"]}, diff)
                                   for r, diff in plan["changed"]])
    held = {t["touch_id"] for t in _all(client, "touches")}
    lost = [r["touch_id"] for r in plan["new"] if r["touch_id"] not in held]
    assert not lost, f"import: {len(lost)} new row(s) not readable after upload: {lost[:5]}"
    affected = {r["contact_id"] for r in plan["new"]} | {r["contact_id"] for r, _ in plan["changed"]}
    plan["resequenced"] = resequence(client, affected)
    for link in ("contacts", "deals", "companies"):   # both ends of each link (loaders._reload)
        client.optimize(link)
    changelog.record(client, "touch", Path(path).name, "imported",
                     f"engagements imported: {len(plan['new'])} new, "
                     f"{len(plan['changed'])} updated from {Path(path).name}")
    search.refresh(client)
    plan["applied"] = True
    return plan


def render_plan(plan: dict) -> str:
    out = [f"rows read: {plan['rows']}"]
    if plan["problems"]:
        by_msg = defaultdict(list)
        for line, msg in plan["problems"]:
            by_msg[msg].append(line)
        out.append(f"REFUSED — {len(plan['problems'])} problem(s); nothing written:")
        for msg, lines in sorted(by_msg.items(), key=lambda kv: -len(kv[1])):
            shown = ", ".join(str(n) for n in lines[:8] if n)
            out.append(f"  {msg}" + (f"  (line {shown}{', …' if len(lines) > 8 else ''})" if shown else ""))
        return "\n".join(out)
    out.append(f"new: {len(plan['new'])}   changed: {len(plan['changed'])}   "
               f"unchanged: {len(plan['unchanged'])}")
    for row, diff in plan["changed"][:10]:
        out.append(f"  ~ {row['touch_id']}: {sorted(diff)}")
    if plan["possible_duplicates"]:
        out.append(f"possible duplicates of hand-logged touches (same contact, channel, day) "
                   f"— imported anyway, check them: {len(plan['possible_duplicates'])}")
        for tid, others in plan["possible_duplicates"][:20]:
            out.append(f"  {tid}  ~  {', '.join(others)}")
    if plan.get("applied"):
        out.append(f"APPLIED. resequenced: {plan['resequenced']}")
    else:
        out.append("PLAN ONLY — nothing written. Add --apply to import.")
    return "\n".join(out)


# --- the weekly KPI view ---------------------------------------------------

def _week(iso_ts: str) -> str:
    y, w, _ = dt.date.fromisoformat(iso_ts[:10]).isocalendar()
    return f"{y}-W{w:02d}"


def _rate(num: int, den: int) -> float | None:
    """None, not 0, when there is nothing to divide: 0/0 is no data."""
    return round(num / den, 3) if den else None


def weekly(client: AitoClient, as_of: dt.date, weeks: int = 8) -> dict:
    """The engagement KPIs per ISO week, the last `weeks` weeks up to `as_of`.
    Every rate carries its denominator, and a rate over nothing is null."""
    start = as_of - dt.timedelta(days=7 * weeks - 1 + as_of.weekday())
    rows = [t for t in _all(client, "touches")
            if start.isoformat() <= t["ts"][:10] <= as_of.isoformat()]
    by_week: dict[str, list[dict]] = defaultdict(list)
    for t in rows:
        by_week[_week(t["ts"])].append(t)
    series = []
    d = start
    while d <= as_of:
        wk = _week(d.isoformat())
        ts = by_week.get(wk, [])
        out = [t for t in ts if t.get("direction") != "in"]
        calls = [t for t in out if t["channel"] == "call"]
        calls_known = [t for t in calls if t.get("answered_by")]
        emails = [t for t in out if t["channel"] == "email"]
        first = [t for t in out if t.get("step") == 1]
        booked = sum(1 for t in ts if t["outcome"] == "meeting_booked")
        series.append({
            "week": wk,
            "engagements": len(ts),
            "by_channel": dict(sorted(Counter(t["channel"] for t in out).items())),
            "inbound": len(ts) - len(out),
            "new_contacts_touched": len(first),
            "calls": len(calls),
            "calls_answered_by_person": _rate(
                sum(1 for t in calls_known if t["answered_by"] == "person"), len(calls_known)),
            "calls_with_answered_by": len(calls_known),
            "emails_out": len(emails),
            "email_replies_in": sum(1 for t in ts if t.get("direction") == "in"
                                    and t["channel"] == "email"),
            "meetings_booked": booked,
            "meetings_held": sum(1 for t in ts if t["channel"] == "meeting"
                                 and t["outcome"] == "conversation"),
            "meetings_per_10_first_touches": (round(10 * booked / len(first), 1)
                                              if first else None),
        })
        d += dt.timedelta(days=7)
    deals = _all(client, "deals")
    open_deals = [x for x in deals if x["stage"] in schema.DEAL_OPEN_STAGES]
    return {
        "as_of": as_of.isoformat(), "weeks": series,
        "open_deals_by_blocker": dict(Counter(x["blocker"] for x in open_deals).most_common()),
        "lost_by_reason": dict(Counter(x.get("lost_reason") or "not recorded"
                                       for x in deals if x["stage"] == "closed_lost").most_common()),
        "with_engagement_details": sum(1 for t in rows if t.get("direction")),
        "in_window": len(rows),
    }
