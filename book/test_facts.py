"""Account facts gate (docs/39, slice 2 of td-20261103224048158692): short,
sourced statements per account, superseded but never deleted, feeding
briefing(company). T1 runs on the synthetic replica the seed generator binds to
a seed account (no real account), plus the CRO's requirements and the partner-hold rules.
Grouping and sorting only, no inference (rule 2); a bad value raises with
the row (rule 3). Requires a running Aito instance.
"""

import re

import booktest as bt

from company_ai import companies, facts, loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

# the seed generator binds the replica and the hold to real seed accounts
# (scripts/generate_seed.py make_facts); the book reads them from the seed, so
# a roster change moves the fixture with it instead of breaking it
SEED = loaders._read_csv(SEED_DIR / "facts.csv")
REPLICA = SEED[0]["company"]
HELD = next(r["company"] for r in SEED if r["kind"] == "hold")
LEAD = SEED[0]["stakeholder_id"]


def F(n: int) -> str:
    """The n-th fact of the seed replica (1-based, as listed in REPLICA_FACTS)."""
    return SEED[n - 1]["fact_id"]


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _seeded() -> AitoClient:
    client = _client()
    loaders.create_schema(client)
    loaders.load_all(client, SEED_DIR)
    return client


def _masked(status: str) -> str:
    """A status with the generated fact ids made stable (fa-<stamp> -> fa-new)."""
    return re.sub(r"fa-\d{20}", "fa-new", status)


def _ids(rows) -> list[str]:
    return [r["source"]["id"] for r in rows]


def _show(t, f: dict) -> None:
    t.tln(f"hold: {f['hold']['status']}")
    for slot, rows in f["roles"].items():
        t.tln(f"  {slot}: {[(r['stakeholder'], r['source_kind'], r['source']['date']) for r in rows]}")
    for c in f["conflicts"]:
        t.tln(f"  CONFLICT {c['slot']}: {_ids(c['facts'])}")
    t.tln(f"  decisions: {[(r['statement'], r['stakeholder'], r['replaces']) for r in f['decisions']]}")
    t.tln(f"  open questions: {[(r['statement'], 'whose move: ' + r['slot']) for r in f['open_questions']]}")
    t.tln(f"  commitments: {[(r['statement'], r['slot'], r['state'], r['due']) for r in f['commitments']]}")
    t.tln(f"  contact info current: {[r['statement'] for r in f['contact_info']['current']]}"
          f"; not current: {[(r['statement'], r['state']) for r in f['contact_info']['not_current']]}")


def test_t1_the_replica_briefing_names_the_decision_owner(t: bt.TestCaseRun) -> None:
    client = _seeded()
    b = companies.briefing(client, REPLICA).derived
    f = b["facts"]
    t.h1(f"briefing({REPLICA!r}): facts")
    _show(t, f)
    # 1. the commercial lead is decision owner, sourced to the 26.10 split
    owners = f["roles"]["decision_owner"]
    lead = [r for r in owners if r["stakeholder_id"] == LEAD]
    assert lead and lead[0]["source_kind"] == "doc" and lead[0]["source"]["date"] == "2026-10-26", owners
    # 2. the sponsor's "decides what is sold" is a conflict in that slot, both sources shown
    assert [(c["slot"], sorted(_ids(c["facts"]))) for c in f["conflicts"]] == \
        [("decision_owner", [F(1), F(2)])], f["conflicts"]
    # 3. the decision mail went to the decision owner; it shows what it replaced
    latest = f["decisions"][0]
    assert latest["source"]["id"] == F(3) and latest["source_kind"] == "mail"
    assert latest["stakeholder_id"] in {r["stakeholder_id"] for r in owners}
    assert latest["replaces"] == [F(11)], latest
    assert F(11) not in _ids(f["decisions"]), "a superseded fact is not active"
    # 4. the champion's buy-or-publish question is an open question, not ownership
    assert F(4) in _ids(f["open_questions"]) and f["open_questions"][0]["slot"] == "theirs"
    assert F(4) not in [i for rows in f["roles"].values() for i in _ids(rows)]

    t.h1("The CRO's requirements on the same briefing")
    # two champions are normal: listed, not a conflict (CPO review of #75)
    assert sorted(_ids(f["roles"]["champion"])) == [F(5), F(6)]
    drafted = [r for r in f["commitments"] if r["state"] == "drafted"]
    assert [r["source"]["id"] for r in drafted] == [F(8)] and drafted[0]["label"] == "drafted, not sent"
    assert _ids(f["contact_info"]["current"]) == [F(10)]
    assert _ids(f["contact_info"]["not_current"]) == [F(9)], "a bounced address is never current"
    assert f["hold"]["status"] is None
    assert b["open_deals"] == [], "facts work on an account with no open deal"
    t.tln("  two champions listed, not flagged; the draft marked not sent; the bounced address apart")


def test_the_partner_hold_fails_closed(t: bt.TestCaseRun) -> None:
    client = _seeded()
    t.h1(f"{HELD}: one hold from antti, no release")
    f = companies.briefing(client, HELD).derived["facts"]
    t.tln(f"  {f['hold']['status']}")
    assert f["hold"]["status"] == "HOLD" and b_first(companies.briefing(client, HELD).derived)

    t.h1("A hold or a release from any other source is refused")
    for source_kind in ("mail", "call", "doc", "touch"):
        try:
            log.add_fact(client, company=HELD, kind="hold", state="released", statement="Released",
                         source_kind=source_kind, source_id="x", valid_from="2026-11-05", author="cro")
            raise AssertionError(f"a {source_kind} release must be refused")
        except AssertionError as e:
            if "must be refused" in str(e):
                raise
            t.tln(f"  {source_kind}: refused: {str(e).split(';')[0]}")

    t.h1("A release from antti, superseding the hold, releases this one account")
    hold = facts.list_facts(client, HELD)[0]
    release = log.add_fact(client, company=HELD, kind="hold", state="released",
                           statement="Released for one meeting", source_kind="antti",
                           source_id="antti-seed-1105", valid_from="2026-11-05", author="antti")
    log.supersede_fact(client, hold["fact_id"], release["fact_id"])
    f = companies.briefing(client, HELD).derived["facts"]
    t.tln(f"  {f['hold']['status']}")
    assert f["hold"]["status"] == "released"

    t.h1("Unclear holds show HOLD (unclear: reason), never released")
    stray = log.add_fact(client, company=REPLICA, kind="hold", state="released",
                         statement="Released", source_kind="antti", source_id="antti-x",
                         valid_from="2026-11-05", author="antti")
    f = companies.briefing(client, REPLICA).derived["facts"]
    t.tln(f"  a release that supersedes nothing: {_masked(f['hold']['status'])}")
    assert f["hold"]["status"] == "HOLD (unclear: a release that supersedes no hold)"
    log.add_fact(client, company=REPLICA, kind="hold", state="on_hold", statement="On partner hold",
                 source_kind="antti", source_id="antti-y", valid_from="2026-11-05", author="antti")
    f = companies.briefing(client, REPLICA).derived["facts"]
    t.tln(f"  two active holds: {_masked(f['hold']['status'])}")
    assert f["hold"]["status"].startswith("HOLD (unclear: two active holds")
    assert any(c["slot"] == "hold" for c in f["conflicts"])
    # a hold row with another source can only arrive by a direct write; it still fails closed
    client.upload_batch("facts", [{**{k: v for k, v in stray.items() if k != "already_recorded"},
                                   "fact_id": "fa-direct-1", "company": HELD,
                                   "company_id": loaders.company_slug(HELD), "source_kind": "mail"}])
    f = companies.briefing(client, HELD).derived["facts"]
    t.tln(f"  a hold row from mail: {_masked(f['hold']['status'])}")
    assert f["hold"]["status"].startswith("HOLD (unclear:") and "source mail" in f["hold"]["status"]

    t.h1("Antti resolves the stray row: his fact supersedes it, and the state is recomputed")
    try:
        log.supersede_fact(client, release["fact_id"], "fa-direct-1")
        raise AssertionError("a foreign-source hold must not supersede Antti's")
    except AssertionError as e:
        if "must not supersede" in str(e):
            raise
        t.tln(f"  the stray row as the new side: refused: {str(e).split(';')[0]}")
    log.supersede_fact(client, "fa-direct-1", release["fact_id"])
    f = companies.briefing(client, HELD).derived["facts"]
    t.tln(f"  after superseding the stray row with Antti's release: {f['hold']['status']}")
    assert f["hold"]["status"] == "released", f["hold"]


def b_first(b: dict) -> bool:
    """The hold is the briefing's first key, so it reads first."""
    return next(iter(b)) == "hold" and b["hold"] == b["facts"]["hold"]["status"]


def test_facts_are_validated_and_superseded_not_deleted(t: bt.TestCaseRun) -> None:
    client = _seeded()
    t.h1("A value outside the per-kind vocabulary is refused with the row")
    bad = [dict(kind="role", slot="cheerleader"), dict(kind="commitment", slot="ours"),
           dict(kind="decision", slot="ours"), dict(kind="gossip"),
           dict(kind="decision", source_kind="rumour"), dict(kind="contact_info", state="maybe")]
    for b in bad:
        args = {**dict(company=REPLICA, statement="x", source_kind="call", source_id="c",
                       valid_from="2026-11-05", author="cro"), **b}
        try:
            log.add_fact(client, **args)
            raise AssertionError(f"{b} must be refused")
        except AssertionError as e:
            if "must be refused" in str(e):
                raise
            t.tln(f"  {b}: {str(e).split(';')[0]}")

    t.h1("A retry inside the window returns the first row")
    one = log.add_fact(client, company=REPLICA, kind="decision", statement="Pilot approved",
                       source_kind="mail", source_id="mail-retry", valid_from="2026-11-06", author="cro")
    two = log.add_fact(client, company=REPLICA, kind="decision", statement="Pilot approved",
                       source_kind="mail", source_id="mail-retry", valid_from="2026-11-06", author="cro")
    assert two["fact_id"] == one["fact_id"] and two.get("already_recorded")
    t.tln("  same fact_id, already_recorded")

    t.h1("Supersede: same company and kind only; the old fact stays, inactive")
    for old, new in ((F(1), F(3)), (F(1), F(12)), (F(11), F(3))):
        try:
            log.supersede_fact(client, old, new)
            raise AssertionError(f"{old}->{new} must be refused")
        except AssertionError as e:
            if "must be refused" in str(e):
                raise
            t.tln(f"  {old} -> {new}: {str(e).split(';')[0]}")
    log.supersede_fact(client, F(2), F(1))
    f = companies.briefing(client, REPLICA).derived["facts"]
    t.tln(f"  after fact 2 -> fact 1: conflicts {f['conflicts']}")
    assert f["conflicts"] == [] and _ids(f["roles"]["decision_owner"]) == [F(1)]
    every = facts.list_facts(client, REPLICA, active_only=False)
    assert any(r["fact_id"] == F(2) and r["superseded_by"] == F(1) for r in every)
    t.tln("  list_facts(active_only=False) still has fact 2, superseded by fact 1")
