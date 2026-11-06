"""Harvesting account facts out of notes (docs/42, td-20261106233617731095):
the `harvest_queue` lookups the Claude session reads from, the `attribute`
kind and the `signer` role (vocabulary confirmed by the CRO), and the hold
guard. The reading itself is the session's, confirmed by a person; the gate
tests the plumbing. Requires a running Aito instance."""

import re

import booktest as bt

from company_ai import companies, facts, graph, loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

SEED = loaders._read_csv(SEED_DIR / "facts.csv")
REPLICA = SEED[0]["company"]
RID = loaders.company_slug(REPLICA)


def _seeded() -> AitoClient:
    config = Config.from_env()
    client = AitoClient(config.instance_url, config.api_key)
    loaders.create_schema(client)
    loaders.load_all(client, SEED_DIR)
    return client


def _note(client: AitoClient) -> str:
    return sorted(h["doc_id"] for h in client.query(
        {"from": "documents", "where": {"company_id": RID}, "select": ["doc_id"], "limit": 100})["hits"])[0]


def test_the_queue_is_lookups_for_the_session_to_read(t: bt.TestCaseRun) -> None:
    client = _seeded()
    q = facts.harvest_queue(client, REPLICA)
    t.h1("harvest_queue(<replica>)")
    t.tln(f"  hold: {q['hold']}")
    for n in q["notes"]:
        t.tln(f"  {n['doc_id']} {n['title']!r}: {len(n['body'])} chars, thin={n['thin']}, "
              f"cited by {n['cited_by']}")
    t.tln(f"  other active facts: {len(q['facts'])}")
    t.tln(f"  requests: {[r.get('from') or r.get('schema') for r in q['requests']]}")
    note = next(n for n in q["notes"] if n["doc_id"] == _note(client))
    cited = {f["fact_id"] for f in SEED if f["source_id"] == note["doc_id"] and not f["superseded_by"]}
    assert set(note["cited_by"]) == cited and {SEED[0]["fact_id"]} <= cited
    assert note["body"] and "Budget cycle" in note["body"]
    active = {f["fact_id"] for f in SEED if f["company"] == REPLICA and not f["superseded_by"]}
    assert {f["fact_id"] for f in q["facts"]} == active - cited, "the account's other active facts"
    assert q["hold"] is None

    t.h1("The seed's note already yields attribute facts")
    attrs = sorted((f["slot"], f["statement"]) for f in SEED if f["kind"] == "attribute")
    for slot, statement in attrs:
        t.tln(f"  {slot}: {statement}")
    assert {s for s, _ in attrs} >= {"budget_cycle", "procurement", "billing_model"}


def test_attributes_and_signers_are_listed_not_conflicts(t: bt.TestCaseRun) -> None:
    client = _seeded()
    doc = _note(client)
    newer = log.add_fact(client, company=REPLICA, kind="attribute", slot="budget_cycle",
                         statement="Budget now set in a February review", source_kind="doc",
                         source_id=doc, valid_from="2026-11-06", author="cro")
    assert newer["warnings"] == []
    signers = [log.add_fact(client, company=REPLICA, kind="role", slot="signer", statement=s,
                            source_kind="doc", source_id=doc, valid_from="2026-11-06", author="cro",
                            stakeholder_id=SEED[0]["stakeholder_id"])
               for s in ("The COO signs the order", "Legal countersigns")]
    b = companies.briefing(client, REPLICA).derived["facts"]
    t.h1("briefing: the attributes group, by slot, newest first")
    for slot, rows in b["attributes"].items():
        t.tln(f"  {slot}: {[r['statement'] for r in rows]}")
    cycle = [r["source"]["id"] for r in b["attributes"]["budget_cycle"]]
    assert cycle[0] == newer["fact_id"] and len(cycle) == 2, "both listed, the newer first"
    t.tln(f"  signers: {[r['statement'] for r in b['roles']['signer']]}")
    assert {r["source"]["id"] for r in b["roles"]["signer"]} == {s["fact_id"] for s in signers}
    t.tln(f"  conflicts: {[c['slot'] for c in b['conflicts']]}")
    assert not [c for c in b["conflicts"] if c["slot"] in ("signer", "budget_cycle")]

    t.h1("In the unfold, the attribute is said in its note")
    net = graph.network(client, focus=RID)
    edge = next(e for e in net["edges"] if e["kind"] == "said_in" and e["source"] == f"fact:{newer['fact_id']}")
    t.tln(f"  {edge['target']}")
    assert edge["target"] == f"document:{doc}"

    t.h1("An unknown attribute slot is refused, naming it")
    try:
        log.add_fact(client, company=REPLICA, kind="attribute", slot="mood", statement="Cheerful",
                     source_kind="doc", source_id=doc, valid_from="2026-11-06", author="cro")
        raise AssertionError("an unknown slot must be refused")
    except AssertionError as e:
        if "must be refused" in str(e):
            raise
        t.tln(f"  {e}".split(" {")[0])
        assert "'mood'" in str(e)


def test_a_held_account_is_not_harvested(t: bt.TestCaseRun) -> None:
    client = _seeded()
    held = next(f for f in SEED if f["kind"] == "hold")["company"]
    q = facts.harvest_queue(client, held)
    t.h1("A held account")
    t.tln(f"  hold: {q['hold']}, notes: {q['notes']}, facts: {q['facts']}")
    assert q["hold"] == "HOLD" and q["notes"] == [] and q["facts"] == []

    t.h1("An unclear hold stops it too")
    log.add_fact(client, company=REPLICA, kind="hold", state="on_hold", statement="Partner hold",
                 source_kind="antti", source_id="antti-1106a", valid_from="2026-11-06", author="antti")
    log.add_fact(client, company=REPLICA, kind="hold", state="on_hold", statement="Partner hold again",
                 source_kind="antti", source_id="antti-1106b", valid_from="2026-11-06", author="antti")
    q = facts.harvest_queue(client, REPLICA)
    t.tln(f"  hold: {re.sub(r'fa-[0-9]+', 'fa-<new>', q['hold'])}, notes: {len(q['notes'])}")
    assert q["hold"].startswith("HOLD (unclear") and q["notes"] == [] and q["facts"] == []
