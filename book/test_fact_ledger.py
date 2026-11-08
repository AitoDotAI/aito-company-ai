"""The fact ledger, slice 1 (docs/43, td-20261108214053518773): every fact in
one list, found by account, kind, slot, the record it cites, or its status,
with that status computed at read. A document edit is in the change log, so a
fact whose note changed after it was attached is due for review. Exact
lookups only, nothing ranked (rule 2); an unknown filter raises (rule 3).
Requires a running Aito instance."""

import re

import booktest as bt

from company_ai import changelog, facts, loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

SEED = loaders._read_csv(SEED_DIR / "facts.csv")
REPLICA = SEED[0]["company"]
RID = loaders.company_slug(REPLICA)


def _seeded() -> AitoClient:
    config = Config.from_env()
    client = AitoClient(config.instance_url, config.api_key)
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
    assert {r["fact_id"] for r in ledger["facts"]} == every, "superseded facts are listed too"
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
