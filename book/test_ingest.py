"""Ingest gate: the agent's add_contact / add_deal writes.

Adding a record validates exactly like a CSV load (bad enums raise) and is
immediately queryable — a new contact shows up in the rolodex, a new deal in
the open pipeline. Writes go to the live Aito instance, never to seed.
Requires a running Aito instance.
"""

import booktest as bt

from company_ai import deals, log, loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def test_add_contact_and_deal(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)

    t.h1("Add a contact")
    before = client.count("contacts")
    row = log.add_contact(
        client, name="Probe Person", company="Probe Oy", role="CFO",
        segment="accounting", tier="A", ai_lifecycle="announced",
        source="referral", country="Finland", phone_present=True,
        email_present=True, notes_tags=["q3-budget"])
    t.tln(f"contact_id prefix: {row['contact_id'].split('-')[0]}")
    t.tln(f"funnel flags start false: "
          f"{[row[k] for k in ('ever_touched','ever_reached','ever_conversation','ever_meeting')]}")
    t.tln(f"phone_present coerced to bool: {row['phone_present']!r}")
    t.tln(f"notes_tags tokenized: {row['notes_tags']!r}")
    assert client.count("contacts") == before + 1
    found = client.query({"from": "contacts", "where": {"contact_id": row["contact_id"]}, "limit": 1})
    t.tln(f"queryable immediately: {found['total'] == 1}")

    t.h1("Add a deal — it enters the open pipeline")
    before_open = deals.pipeline(client).derived["kpis"]["open_deals"]
    deal = log.add_deal(client, company="Probe Oy", segment="accounting",
                        stage="qualified", value_eur=40000, probability=55,
                        champion_present=True, blocker="none")
    t.tln(f"won derived from stage 'qualified': {deal['won']}")
    after = deals.pipeline(client).derived
    after_open = after["kpis"]["open_deals"]
    assert after_open == before_open + 1, "new deal not in open pipeline"
    t.tln(f"open deals {before_open} -> {after_open}")
    mine = [d for d in after["deals"] if d["deal_id"] == deal["deal_id"]]
    t.tln(f"new deal ranked with a close-likelihood: p_win={mine[0]['p_win'] is not None}")


def test_add_todo_post_session(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    for tbl in ("todos", "posts", "sessions"):
        loaders.clear_table(client, tbl)

    # link a real deal + a stakeholder at its company (live links are validated)
    deal = client.query({"from": "deals", "where": {"won": None}, "limit": 1})["hits"][0]
    contact = client.query({"from": "contacts", "where": {"company": deal["company"]},
                            "limit": 1})["hits"]
    stakeholder = contact[0]["contact_id"] if contact else None

    t.h1("add_todo (sales, action_type, linked deal + stakeholder)")
    td = log.add_todo(client, area="sales", title=f"Call {deal['company']}", priority=1,
                      action_type="call", due_date="2026-06-20", window="fri_1430",
                      linked_type="deal", linked_id=deal["deal_id"], stakeholder_id=stakeholder)
    t.tln(f"id prefix={td['todo_id'].split('-')[0]} area={td['area']} "
          f"action_type={td['action_type']} linked={td['linked_type']} "
          f"stakeholder_set={bool(td['stakeholder_id'])} status={td['status']}")
    assert client.query({"from": "todos", "where": {"todo_id": td["todo_id"]}, "limit": 1})["total"] == 1

    t.h1("add_todo rejects a dangling deal link (live validation)")
    try:
        log.add_todo(client, area="sales", title="x", priority=1, due_date="2026-06-20",
                     window="fri_1430", linked_type="deal", linked_id="no-such-deal")
        raise RuntimeError("accepted a dangling deal link")
    except AssertionError as e:
        t.tln(str(e).split(";")[0])

    t.h1("marketing: material → channel → plan a post → record the result")
    mat = log.add_material(client, type="blog", title="Positioning teardown",
                           topic="positioning", lane="warm", ai_made="manual", length_chars=320)
    ch = log.add_channel(client, name="LinkedIn", platform="linkedin")
    po = log.add_post(client, material_id=mat["material_id"], channel_id=ch["channel_id"],
                      tone="narrate", format="text", link_placement="comment")
    t.tln(f"planned: status={po['status']} platform={po['platform']} "
          f"ai_made(from material)={po['ai_made']} length_bucket={po['length_bucket']} won={po['won']}")
    done = log.log_post_result(client, po["post_id"], outcome="win",
                               reach_or_views=1840, upvotes=31, posted_at="2026-06-17")
    t.tln(f"posted: status={done['status']} weekday={done['weekday']} won={done['won']}")

    t.h1("log_session (monotone stages)")
    se = log.log_session(client, source="referral", landing_page="/demo",
                         country="Finland", device="desktop", signed_up=True,
                         started_trial=True, converted_paid=False)
    t.tln(f"signed_up={se['signed_up']} started_trial={se['started_trial']} "
          f"converted_paid={se['converted_paid']}")


def test_add_validates_loudly(t: bt.TestCaseRun) -> None:
    t.h1("Bad enum values raise (no silent ingest)")
    client = _client()
    cases = {
        "unknown segment": lambda: log.add_contact(
            client, name="X", company="Y", role="Z", segment="crypto", tier="A",
            ai_lifecycle="none", source="cold", country="FI",
            phone_present=False, email_present=False),
        "unknown deal stage": lambda: log.add_deal(
            client, company="Y", segment="erp", stage="closed_perhaps",
            value_eur=1000, probability=50, champion_present=False),
        "probability out of range": lambda: log.add_deal(
            client, company="Y", segment="erp", stage="lead",
            value_eur=1000, probability=150, champion_present=False),
    }
    for label, fn in cases.items():
        try:
            fn()
            raise RuntimeError(f"{label}: was accepted")
        except AssertionError as e:
            t.tln(f"{label}: {str(e).split(';')[0]}")
