"""Users & assignees (docs/27): a small team over a shared CRM.

Proves the Phase-1 contract the UI/MCP/identity all sit on: the roster loads,
an email resolves to a user (the Easy Auth identity mapping), work is assigned
across contacts/todos/deals through the join table (the big CRM tables never
change), "my work" reads it back, and the invalid cases raise (rule 3).

Prints stay id/date-free (assignment_id + created are stamped) for a stable
snapshot. Requires a running Aito.
"""

import booktest as bt

from company_ai import loaders, log, users
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _load(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_users(client, SEED_DIR)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_todos(client, SEED_DIR)


def test_roster_and_identity(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)

    t.h1("the roster (operator first), and identity from an email")
    for u in users.list_users(client):
        t.tln(f"  [{u['role']}] {u['name']} <{u['email']}>")
    t.tln(f"resolve 'ALEX@example.com' -> {(users.resolve(client, 'ALEX@example.com') or {}).get('role')}")
    t.tln(f"resolve 'nobody@example.com'     -> {users.resolve(client, 'nobody@example.com')}")


def test_assign_across_entities_and_my_work(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    cid = client.query({"from": "contacts", "limit": 1})["hits"][0]["contact_id"]
    did = client.query({"from": "deals", "limit": 1})["hits"][0]["deal_id"]
    tid = client.query({"from": "todos", "limit": 1})["hits"][0]["todo_id"]

    t.h1("assign a lead, a deal, and a task to the SDR")
    log.set_assignment(client, "contacts", cid, "u_sdr")
    log.set_assignment(client, "deals", did, "u_sdr")
    log.set_assignment(client, "todos", tid, "u_sdr")
    mine = users.my_work(client, "u_sdr").derived
    t.tln(f"sdr my_work: {mine['count']} items "
          f"(contacts {len(mine['contacts'])}, deals {len(mine['deals'])}, todos {len(mine['todos'])})")

    t.h1("reassign the lead to the operator, unassign the deal")
    log.set_assignment(client, "contacts", cid, "u_operator")
    log.set_assignment(client, "deals", did, None)
    sdr, op = users.my_work(client, "u_sdr").derived, users.my_work(client, "u_operator").derived
    t.tln(f"sdr now: {sdr['count']} (the task)")
    t.tln(f"operator now: {op['count']} (the lead)")
    amap = users.assignment_map(client)
    t.tln("assignment map (entity -> owner):")
    for (entity, _id), uid in sorted(amap.items()):
        t.tln(f"  {entity} -> {uid}")

    t.h1("the CRM tables are untouched by assignment (join table only)")
    t.tln(f"contacts still: {client.count('contacts')}, deals: {client.count('deals')}, "
          f"todos: {client.count('todos')}")


def test_invalid_assignments_raise(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    tid = client.query({"from": "todos", "limit": 1})["hits"][0]["todo_id"]

    t.h1("invalid assignments raise (rule 3)")
    for label, call in {
        "unknown user": lambda: log.set_assignment(client, "todos", tid, "u_ghost"),
        "bad entity": lambda: log.set_assignment(client, "widgets", tid, "u_sdr"),
        "unknown item": lambda: log.set_assignment(client, "todos", "nope", "u_sdr"),
        "duplicate email": lambda: log.add_user(client, "Dup", "alex@example.com"),
    }.items():
        try:
            call()
            t.tln(f"  {label}: NOT refused (bug)")
        except AssertionError as e:
            t.tln(f"  {label}: {str(e)[:60]}")
