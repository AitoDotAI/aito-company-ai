"""The fact ledger, slice 1 (docs/43, td-20261108214053518773): every fact in
one list, found by account, kind, slot, the record it cites, or its status,
with that status computed at read. A document edit is in the change log, so a
fact whose note changed after it was attached is due for review. Exact
lookups only, nothing ranked (rule 2); an unknown filter raises (rule 3).
Requires a running Aito instance."""

import re
from datetime import datetime

import booktest as bt

from book._target import guarded_client
from company_ai import changelog, facts, loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR

SEED = loaders._read_csv(SEED_DIR / "facts.csv")
REPLICA = SEED[0]["company"]
RID = loaders.company_slug(REPLICA)


def _seeded() -> AitoClient:
    client = guarded_client()   # refuses anything but a test env, before any call
    # the seed carries no change log, and edits from earlier runs would read as
    # edits to the freshly seeded notes; start it empty, as the changelog book does
    client.delete_table("changelog")
    loaders.create_schema(client)
    loaders.load_all(client, SEED_DIR)
    return client


def _id(fact_id: str) -> str:
    """A fact id with a generated stamp made stable (fa-<stamp> -> fa-new)."""
    return re.sub(r"fa-\d{20}", "fa-new", fact_id)


def _show(t: bt.TestCaseRun, ledger: dict) -> None:
    for r in ledger["facts"]:
        slot = f"/{r['slot']}" if r.get("slot") else ""
        t.tln(f"  {_id(r['fact_id'])} {r['kind']}{slot}: {r['statement']!r}")
        t.tln(f"      source {r['source']['kind']}:{r['source']['id']} ({r['source']['status']}), "
              f"status: {r['status']}")
    t.tln(f"  requests: {[r.get('from') for r in ledger['requests']]}")


def test_one_account_lists_every_fact_with_its_status(t: bt.TestCaseRun) -> None:
    client = _seeded()
    ledger = facts.ledger(client, company=REPLICA)
    t.h1("ledger(company=<replica>)")
    _show(t, ledger)
    every = {f["fact_id"] for f in SEED if f["company"] == REPLICA}
    assert {r["fact_id"] for r in ledger["facts"] if r["kind"] != "derived"} == every, \
        "superseded facts are listed too"
    assert [r["kind"] for r in ledger["facts"]].count("derived") == 1, "beside one derived status row"
    by_id = {r["fact_id"]: r for r in ledger["facts"]}
    for f in SEED:
        if f["company"] == REPLICA:
            want = "superseded" if f["superseded_by"] else "active"
            assert by_id[f["fact_id"]]["status"] == want, (f, by_id[f["fact_id"]])
    assert all(r["source"]["status"] != "dangling" for r in ledger["facts"])


def test_a_record_id_finds_the_facts_that_cite_it(t: bt.TestCaseRun) -> None:
    client = _seeded()
    doc = next(f["source_id"] for f in SEED if f["company"] == REPLICA and f["source_kind"] == "doc")
    ledger = facts.ledger(client, source_id=doc)
    t.h1("ledger(source_id=<the replica's note>)")
    _show(t, ledger)
    cites = {f["fact_id"] for f in SEED if f["source_id"] == doc}
    assert {r["fact_id"] for r in ledger["facts"]} == cites and cites
    assert facts.ledger(client, source_id="no-such-record")["facts"] == []


def test_filters_narrow_and_an_unknown_one_raises(t: bt.TestCaseRun) -> None:
    client = _seeded()
    t.h1("ledger(company=<replica>, kind=attribute)")
    attrs = facts.ledger(client, company=REPLICA, kind="attribute")
    _show(t, attrs)
    assert attrs["facts"] and {r["kind"] for r in attrs["facts"]} == {"attribute"}
    t.h1("ledger(company=<replica>, status=superseded)")
    old = facts.ledger(client, company=REPLICA, status="superseded")
    _show(t, old)
    assert {r["fact_id"] for r in old["facts"]} == {
        f["fact_id"] for f in SEED if f["company"] == REPLICA and f["superseded_by"]}
    for bad in ({"kind": "rumour"}, {"status": "stale"}, {"slot": "favourite_colour"}):
        try:
            facts.ledger(client, company=REPLICA, **bad)
        except AssertionError as e:
            t.tln(f"  {bad} -> refused: {e}")
        else:
            raise AssertionError(f"{bad} was accepted")


def test_a_note_edited_after_a_fact_was_attached_puts_it_up_for_review(t: bt.TestCaseRun) -> None:
    client = _seeded()
    doc = next(f["source_id"] for f in SEED if f["company"] == REPLICA and f["source_kind"] == "doc")
    before = {r["fact_id"] for r in facts.ledger(client, source_id=doc, status="active")["facts"]}
    assert before

    log.update_document(client, doc, {"title": "Account plan (typo fixed)"})
    t.h1("update_document writes a change-log row")
    logged = changelog.recent(client, entity="documents", limit=5)["changes"]
    mine = [c for c in logged if c["entity_id"] == doc]
    t.tln(f"  {[(c['entity'], c['action'], c['summary']) for c in mine[:1]]}")
    assert mine and mine[0]["action"] == "updated", logged

    after = log.add_fact(client, company=REPLICA, kind="attribute", slot="tooling",
                         statement="Runs the reporting in a spreadsheet", source_kind="doc",
                         source_id=doc, valid_from="2026-11-08", author="cro")
    ledger = facts.ledger(client, source_id=doc)
    t.h1("ledger(source_id=<the edited note>)")
    _show(t, ledger)
    status = {r["fact_id"]: r["status"] for r in ledger["facts"]}
    assert {i for i in before if status[i] == "review: source changed"} == before
    assert status[after["fact_id"]] == "active", "attached after the edit: not flagged"
    flagged = facts.ledger(client, company=REPLICA, status="review: source changed")["facts"]
    assert {r["fact_id"] for r in flagged} == before


def test_a_source_that_names_nothing_is_up_for_review(t: bt.TestCaseRun) -> None:
    client = _seeded()
    lost = log.add_fact(client, company=REPLICA, kind="attribute", slot="headcount",
                        statement="About forty people", source_kind="doc", source_id="sdc-missing",
                        valid_from="2026-11-08", author="cro")
    row = next(r for r in facts.ledger(client, company=REPLICA)["facts"] if r["fact_id"] == lost["fact_id"])
    t.h1("a doc source that isn't stored")
    t.tln(f"  {_id(row['fact_id'])}: source {row['source']['status']}, status: {row['status']}")
    assert (row["source"]["status"], row["status"]) == ("dangling", "review: source missing")


def test_customer_status_is_listed_as_a_derived_row(t: bt.TestCaseRun) -> None:
    """docs/43 §1: customer status is derived from the deals, never written.
    The ledger lists it as a read-only row per account with a won deal,
    citing every won deal; filtered to an account with none it says "no won
    deal on record", never "not a customer"; a deal id finds the row citing it."""
    client = _seeded()
    deals = loaders._read_csv(SEED_DIR / "deals.csv")
    won: dict[str, list[str]] = {}
    for d in deals:
        if d["stage"] == "closed_won":
            won.setdefault(loaders.company_slug(d["company"]), []).append(d["deal_id"])
    derived = facts.ledger(client, kind="derived")
    t.h1("ledger(kind=derived): one row per account with a won deal")
    for r in derived["facts"][:5]:
        t.tln(f"  {r['company_id']}: {r['statement']!r} sources {[s['id'] for s in r['sources']]} [{r['status']}]")
    t.tln(f"  ... {derived['count']} rows")
    assert {r["company_id"]: sorted(s["id"] for s in r["sources"]) for r in derived["facts"]} == \
        {k: sorted(v) for k, v in won.items()}
    assert all(r["status"] == "derived" and r["slot"] == "customer_status" for r in derived["facts"])

    mine = facts.ledger(client, company=REPLICA, kind="derived")
    t.h1("ledger(company=<replica>, kind=derived): it has no won deal")
    for r in mine["facts"]:
        t.tln(f"  {r['statement']!r} [{r['status']}]")
    assert RID not in won
    assert [r["statement"] for r in mine["facts"]] == [
        "No won deal on record (direct deals only; indirect relationships are not shown yet)"]

    deal = sorted(won[next(iter(sorted(won)))])[0]
    by_deal = facts.ledger(client, source_id=deal)
    t.h1("ledger(source_id=<a won deal>)")
    for r in by_deal["facts"]:
        t.tln(f"  {r['company_id']}: {r['statement']!r}")
    assert [r["kind"] for r in by_deal["facts"]] == ["derived"]

    every = facts.ledger(client)
    assert {r["kind"] for r in every["facts"]} >= {"derived", "attribute"}, "listed beside written facts"
    assert facts.ledger(client, status="active")["facts"] and all(
        r["kind"] != "derived" for r in facts.ledger(client, status="active")["facts"])


def test_a_touch_after_the_win_does_not_move_the_status_date(t: bt.TestCaseRun) -> None:
    """The derived row is dated by when the account became a customer: its
    earliest win from deal_events, else the won deal's `created`, and the row
    names which. A later touch on the deal (which moves its last_touch_date)
    must not move it (CPO review of #98)."""
    client = _seeded()
    row = facts.ledger(client, kind="derived")["facts"][0]
    deal = row["sources"][0]["id"]
    contact = client.query({"from": "contacts", "where": {"company_id": row["company_id"]},
                            "limit": 1})["hits"][0]["contact_id"]
    t.h1("a derived row, before and after a touch on its won deal")
    t.tln(f"  before: valid_from {row['valid_from']} ({row['valid_from_field']})")
    log.log_touch(client, contact, "email", None, "reply", deal_id=deal, direction="in",
                  ts=datetime.fromisoformat("2026-11-10T10:00:00"))
    after = next(r for r in facts.ledger(client, kind="derived")["facts"] if r["fact_id"] == row["fact_id"])
    t.tln(f"  after:  valid_from {after['valid_from']} ({after['valid_from_field']})")
    assert after["valid_from"] == row["valid_from"] != "2026-11-10"
    assert row["valid_from_field"] in ("deal_events.date", "deals.created")
