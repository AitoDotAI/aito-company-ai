"""Briefing gate (td-20261103224048158692, slice 1): briefing(company) is the
current state of one account in one read — the company row, its open deals
with their recorded next step, the latest touches and notes, the open todos
linked to it, and its stakeholders. Every fact carries its source (kind, id,
date) and nothing is inferred: it is grouping and formatting over Aito
queries (rule 2). Requires a running Aito instance.
"""

from datetime import date, datetime

import booktest as bt

from company_ai import companies, loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

ACCOUNT = "Briefing Replica Oy"   # synthetic: no real account in the repo
NO_DEAL = "Briefing Nodeal Oy"


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _person(client, name, company, role):
    return log.add_contact(client, name=name, company=company, role=role, segment="consultancy",
                           tier="A", ai_lifecycle="announced", source="warm", country="FI",
                           phone_present=True, email_present=True)


def _account(client) -> dict:
    lead = _person(client, "Replica Lead", ACCOUNT, "Commercial lead")
    sponsor = _person(client, "Replica Sponsor", ACCOUNT, "CTO")
    open_deal = log.add_deal(client, company=ACCOUNT, segment="consultancy", stage="pilot",
                             value_eur=24000, probability=40, champion_present=True,
                             created="2026-10-01", as_of=date(2026, 10, 1))
    lost = log.add_deal(client, company=ACCOUNT, segment="consultancy", stage="closed_lost",
                        value_eur=8000, probability=10, champion_present=False,
                        blocker="budget", created="2026-03-01", as_of=date(2026, 3, 1))
    log.log_touch(client, sponsor["contact_id"], channel="meeting", window="1215", outcome="conversation",
                  notes="Sponsor asked about build versus buy.", ts=datetime(2026, 10, 9, 12, 30))
    log.log_touch(client, lead["contact_id"], channel="email", window="0800", outcome="reply",
                  notes="Lead owns the commercial track from now on.", ts=datetime(2026, 10, 26, 8, 10))
    log.log_touch(client, lead["contact_id"], channel="email", window="1600", outcome="reply",
                  next_action="send the pilot scope", next_action_due="2026-11-04",
                  notes="Decision mail sent to the lead.", deal_id=open_deal["deal_id"],
                  direction="out", ts=datetime(2026, 11, 2, 16, 5))
    log.add_document(client, title="Replica: commercial split", body="Lead owns commercial; sponsor technical.",
                     kind="internal", area="sales", company=ACCOUNT, noted_on="2026-10-26")
    log.add_document(client, title="Replica: kickoff notes", body="First meeting.",
                     kind="internal", area="sales", company=ACCOUNT, noted_on="2026-10-09")
    todos = [
        log.add_todo(client, area="operations", title="Replica: draft the pilot scope", priority=2,
                     linked_type="deal", linked_id=open_deal["deal_id"]),
        log.add_todo(client, area="operations", title="Replica: intro call with the sponsor", priority=3,
                     stakeholder_id=sponsor["contact_id"]),
        log.add_todo(client, area="operations", title="Replica: old follow-up, done", priority=3,
                     status="done", linked_type="deal", linked_id=open_deal["deal_id"]),
        log.add_todo(client, area="operations", title="Replica: post-mortem on the lost deal", priority=3,
                     linked_type="deal", linked_id=lost["deal_id"])]
    other = _person(client, "Nodeal Person", NO_DEAL, "CEO")
    log.log_touch(client, other["contact_id"], channel="call", window="1215", outcome="no_answer",
                  ts=datetime(2026, 10, 20, 12, 15))
    return {"lead": lead, "sponsor": sponsor, "open": open_deal, "lost": lost, "other": other,
            "todos": [x["todo_id"] for x in todos]}


def _cleanup(client, ids: dict) -> None:
    """The fixture's rows go, so no later book reads them."""
    people = [ids[k]["contact_id"] for k in ("lead", "sponsor", "other")]
    for cid in people:
        client.delete_entries("touches", {"contact_id": cid})
        client.delete_entries("contacts", {"contact_id": cid})
    for k in ("open", "lost"):
        client.delete_entries("deal_events", {"deal_id": ids[k]["deal_id"]})
        client.delete_entries("deals", {"deal_id": ids[k]["deal_id"]})
    for tid in ids["todos"]:
        client.delete_entries("todos", {"todo_id": tid})
    for slug in ("briefing-replica-oy", "briefing-nodeal-oy"):
        client.delete_entries("documents", {"company_id": slug})
        client.delete_entries("companies", {"company_id": slug})


def _show(t, b: dict) -> None:
    c = b["company"]
    t.tln(f"company: {c['name']} [{c['source']['kind']}:{c['source']['id']}]")
    t.tln("open deals:")
    for d in b["open_deals"]:
        ns = d["next_step"]
        t.tln(f"  {d['stage']} {d['value_eur']} EUR [{d['source']['kind']}:{d['source']['date']}]"
              f" next: {ns['text'] + ' by ' + str(ns['due']) + ' [touch ' + ns['source']['date'] + ']' if ns else None}"
              f" todos: {[x['title'] for x in d['todos']]}")
    t.tln("stakeholders:")
    for s in b["stakeholders"]:
        last = s["last_touch"]
        t.tln(f"  {s['name']} ({s['role']}) last touch {last['date'] if last else None}")
    t.tln("touches (newest first):")
    for x in b["touches"]:
        t.tln(f"  {x['source']['date']} {x['channel']:7} {x['outcome']:12} {x['contact']}: {x['notes']}")
    t.tln("notes (by noted_on):")
    for n in b["notes"]:
        t.tln(f"  {n['source']['date']} {n['title']}")
    t.tln("open todos:")
    for x in b["todos"]:
        t.tln(f"  {x['title']} [{x['linked'].split(':')[0]}]")


def test_briefing_is_the_account_state_in_one_read(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_touches(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)
    loaders.load_todos(client, SEED_DIR)
    ids = _account(client)

    res = companies.briefing(client, ACCOUNT)
    b = res.derived
    t.h1("The Aito requests (table, the where's shape, hits)")
    for _, request, response in res.calls:
        where = request.get("where", {})
        shape = sorted(where) if "$or" not in where else f"$or of {len(where['$or'])}"
        t.tln(f"  _query {request['from']:10} where {shape} -> {len(response['hits'])} hits")
    t.h1(f"briefing({ACCOUNT!r})")
    _show(t, b)
    assert [d["deal_id"] for d in b["open_deals"]] == [ids["open"]["deal_id"]], "only open deals"
    step = b["open_deals"][0]["next_step"]
    assert step and step["text"] == "send the pilot scope" and step["source"]["kind"] == "touch"
    assert [x["title"] for x in b["open_deals"][0]["todos"]] == ["Replica: draft the pilot scope"], \
        "a done todo is not open"
    assert [x["source"]["date"][:10] for x in b["touches"]] == ["2026-11-02", "2026-10-26", "2026-10-09"]
    assert [n["source"]["date"] for n in b["notes"]] == ["2026-10-26", "2026-10-09"]
    titles = {x["title"] for x in b["todos"]}
    assert titles == {"Replica: draft the pilot scope", "Replica: intro call with the sponsor",
                      "Replica: post-mortem on the lost deal"}, titles
    lead = next(s for s in b["stakeholders"] if s["contact_id"] == ids["lead"]["contact_id"])
    assert lead["last_touch"]["date"][:10] == "2026-11-02"
    for group in ("open_deals", "stakeholders", "touches", "notes", "todos"):
        for row in b[group]:
            assert row["source"]["id"] and row["source"]["kind"], (group, row)

    t.h1(f"briefing({NO_DEAL!r}): an account with no deal row")
    nd = companies.briefing(client, NO_DEAL).derived
    _show(t, nd)
    assert nd["open_deals"] == [] and len(nd["touches"]) == 1 and nd["stakeholders"]

    t.h1("an unknown company is an error, never an empty briefing")
    try:
        companies.briefing(client, "No Such Company Oy")
        raise AssertionError("an unknown company must raise")
    except LookupError as e:
        t.tln(f"  LookupError: {e}")
    _cleanup(client, ids)
