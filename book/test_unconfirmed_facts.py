"""Unconfirmed facts (docs/43 §3, td-20261118105636099520 part 2): an agent
may write a fact, and it reads "unconfirmed (<author>)" everywhere until a
person confirms it. add_fact never sets confirmed_by; only confirm_fact does,
and that tool is kept off the remote surface, so a remote or prompt-injected
session can't certify its own fact (CPO review, 18.11.2026). The confirmer
comes from the local operator's config, never from an argument. Requires a
running Aito instance."""

import dataclasses
import inspect
import re

import booktest as bt

from company_ai import companies, facts, graph, loaders, log, queries, server
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config
from company_ai.remotemcp import REMOTE_DENY

SEED = loaders._read_csv(SEED_DIR / "facts.csv")
ACCOUNT = SEED[0]["company"]
AID = loaders.company_slug(ACCOUNT)
CONTACT = SEED[0]["stakeholder_id"]
OPERATOR = "alex@example.com"


def _seeded() -> AitoClient:
    config = Config.from_env()
    client = AitoClient(config.instance_url, config.api_key)
    loaders.create_schema(client)
    loaders.load_all(client, SEED_DIR)
    return client


def _rows(groups: dict) -> list[dict]:
    """Every row in a briefing-shaped facts group."""
    out = list(groups["hold"]["facts"])
    for rows in (*groups["roles"].values(), *groups["attributes"].values(), groups["decisions"],
                 groups["open_questions"], groups["commitments"], *groups["contact_info"].values()):
        out += rows
    return out


def _marks(groups: dict) -> dict[str, str | None]:
    return {r["source"]["id"]: r["unconfirmed"] for r in _rows(groups)}


def _masked(text: str) -> str:
    """Generated fact ids and timestamps made stable for the snapshot."""
    return re.sub(r"\d{4}-\d\d-\d\dT[\d:]+\+00:00", "<at>", re.sub(r"fa-\d{20}", "fa-new", text))


def _write(client: AitoClient) -> dict:
    return log.add_fact(client, company=ACCOUNT, kind="attribute", slot="volume",
                        statement="About 10 million rows a year", source_kind="call",
                        source_id="call-1811", valid_from="2026-11-18", author="cro")


def test_the_seed_has_confirmed_facts_and_one_unconfirmed(t: bt.TestCaseRun) -> None:
    t.h1("data/seed/facts.csv")
    for f in SEED:
        t.tln(f"  {f['fact_id']} by {f['author']}: confirmed_by {f['confirmed_by'] or None}")
    unconfirmed = [f["fact_id"] for f in SEED if not f["confirmed_by"]]
    assert len(unconfirmed) == 1 and unconfirmed[0] == SEED[-1]["fact_id"]
    assert all(f["confirmed_at"] for f in SEED if f["confirmed_by"])


def test_a_written_fact_reads_unconfirmed_everywhere(t: bt.TestCaseRun) -> None:
    client = _seeded()
    row = _write(client)
    fid = row["fact_id"]
    t.h1("add_fact writes it unconfirmed")
    t.tln(f"  confirmed_by: {row['confirmed_by']}, confirmed_at: {row['confirmed_at']}")
    assert row["confirmed_by"] is None and row["confirmed_at"] is None

    t.h1("briefing, opener_context and company_detail mark it")
    for name, groups in (("briefing", companies.briefing(client, ACCOUNT).derived["facts"]),
                         ("opener_context", queries.opener_context(client, CONTACT).derived["account"]["facts"]),
                         ("company_detail", companies.detail(client, AID).derived["account_facts"])):
        marks = _marks(groups)
        t.tln(f"  {name}: {marks[fid]}; others marked: "
              f"{sorted(k for k, v in marks.items() if v and k != fid)}")
        assert marks[fid] == "unconfirmed (cro)"
        assert {k for k, v in marks.items() if v} == {fid, SEED[-1]["fact_id"]} & set(marks)

    t.h1("the ledger lists it as unconfirmed, and filters on it")
    led = {r["fact_id"]: r["status"] for r in facts.ledger(client, company=ACCOUNT)["facts"]}
    t.tln(f"  fa-new: {led[fid]}")
    assert led[fid] == "unconfirmed"
    only = facts.ledger(client, company=ACCOUNT, status="unconfirmed")["facts"]
    assert {r["fact_id"] for r in only} == {fid} | ({SEED[-1]["fact_id"]} & set(led))

    t.h1("the unfold marks its node")
    node = graph.network(client, focus=AID)["nodes"]
    node = next(n for n in node if n["id"] == f"fact:{fid}")
    t.tln(f"  fact:fa-new: unconfirmed={node['unconfirmed']}")
    assert node["unconfirmed"] == "unconfirmed (cro)"


def test_an_unconfirmed_fact_under_review_is_still_listed_as_unconfirmed(t: bt.TestCaseRun) -> None:
    """A row has one status, and review outranks unconfirmed; the field
    `unconfirmed` says it apart, and the unconfirmed filter reads the field
    (CPO review of #107)."""
    client = _seeded()
    note = sorted(h["doc_id"] for h in client.query(
        {"from": "documents", "where": {"company_id": AID}, "select": ["doc_id"], "limit": 100})["hits"])[0]
    row = log.add_fact(client, company=ACCOUNT, kind="attribute", slot="stack",
                       statement="Python services over Postgres", source_kind="doc", source_id=note,
                       valid_from="2026-11-18", author="cro")
    import time
    time.sleep(1.1)   # created_at and the change log are to the second
    log.update_document(client, note, {"title": "Account plan (edited)"})
    led = {r["fact_id"]: r for r in facts.ledger(client, company=ACCOUNT)["facts"]}
    mine = led[row["fact_id"]]
    t.h1("A fact both unconfirmed and under review")
    t.tln(f"  status: {mine['status']}; unconfirmed: {mine['unconfirmed']}")
    assert mine["status"] == "review: source changed" and mine["unconfirmed"] == "unconfirmed (cro)"
    t.h1("The unconfirmed filter still finds it")
    only = {r["fact_id"] for r in facts.ledger(client, company=ACCOUNT, status="unconfirmed")["facts"]}
    t.tln(f"  found: {row['fact_id'] in only}; with the seed's sfa016: {SEED[-1]['fact_id'] in only}")
    assert only == {row["fact_id"], SEED[-1]["fact_id"]}
    assert all(r["unconfirmed"] is None for r in led.values()
               if r["kind"] != "derived" and r["fact_id"] not in only and not r.get("superseded_by"))


def test_only_confirm_fact_confirms(t: bt.TestCaseRun) -> None:
    client = _seeded()
    t.h1("add_fact takes no confirmed_by: a caller can't certify its own fact")
    params = set(inspect.signature(log.add_fact).parameters) | set(inspect.signature(server.add_fact).parameters)
    t.tln(f"  confirmed_by among add_fact's parameters: {'confirmed_by' in params}")
    assert "confirmed_by" not in params and "confirmed_at" not in params

    row = _write(client)
    fid = row["fact_id"]
    t.h1("confirm_fact records who and when")
    done = log.confirm_fact(client, fid, by=OPERATOR)
    t.tln(f"  confirmed_by {done['confirmed_by']}, confirmed_at set: {bool(done['confirmed_at'])}")
    assert done["confirmed_by"] == OPERATOR and done["confirmed_at"]
    assert _marks(companies.briefing(client, ACCOUNT).derived["facts"])[fid] is None
    led = {r["fact_id"]: r["status"] for r in facts.ledger(client, company=ACCOUNT)["facts"]}
    assert led[fid] == "active"
    changes = client.query({"from": "changelog", "where": {"entity_id": fid, "action": "confirmed"},
                            "limit": 10})["total"]
    t.tln(f"  change-log rows: {changes}")
    assert changes == 1

    t.h1("Refused, naming the fact")
    for label, call in (("twice", lambda: log.confirm_fact(client, fid, by=OPERATOR)),
                        ("unknown id", lambda: log.confirm_fact(client, "fa-none", by=OPERATOR)),
                        ("no confirmer", lambda: log.confirm_fact(client, SEED[-1]["fact_id"], by=""))):
        try:
            call()
            raise AssertionError(f"{label} must be refused")
        except AssertionError as e:
            if "must be refused" in str(e):
                raise
            t.tln(f"  {label}: {_masked(str(e))}")


def test_confirm_fact_is_local_only_and_names_the_operator(t: bt.TestCaseRun) -> None:
    t.h1("The MCP tool")
    t.tln(f"  confirm_fact parameters: {list(inspect.signature(server.confirm_fact).parameters)}")
    t.tln(f"  on the remote surface: {'confirm_fact' not in REMOTE_DENY}")
    assert list(inspect.signature(server.confirm_fact).parameters) == ["fact_id"]
    assert "confirm_fact" in REMOTE_DENY

    t.h1("The confirmer is the configured operator, else refused")
    base = Config.from_env()
    t.tln(f"  with an operator email: {server.confirmer(dataclasses.replace(base, operator_email=OPERATOR))}")
    assert server.confirmer(dataclasses.replace(base, operator_email=OPERATOR)) == OPERATOR
    try:
        server.confirmer(dataclasses.replace(base, operator_email=""))
        raise AssertionError("no operator must be refused")
    except AssertionError as e:
        if "must be refused" in str(e):
            raise
        t.tln(f"  without: {e}")
