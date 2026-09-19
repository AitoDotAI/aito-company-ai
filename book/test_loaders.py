"""Phase A loader gate (docs/04-testing.md gate 1).

Loads both seed datasets into the configured Aito instance, prints
counts and sample rows fetched back from Aito, and relies on the
loaders' own row-count assertions: rows in must equal rows loaded.
Requires a running Aito instance (see README quickstart).
"""

import csv
import json

import booktest as bt

from company_ai import loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, SEED_TINY_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _file_ids(data_dir, filename, id_field, n=5):
    with open(data_dir / filename, newline="", encoding="utf-8") as f:
        return [row[id_field] for row in csv.DictReader(f)][:n]


def _load_and_snapshot(t: bt.TestCaseRun, data_dir) -> None:
    client = _client()
    t.h2("Schema")
    # create_schema's create/add report depends on the instance's prior state
    # (order-dependent across tests); it's pinned deterministically in
    # test_schema_migration. Here we only need the tables to exist.
    loaders.create_schema(client)

    t.h2("Load")
    n_contacts = loaders.load_rolodex(client, data_dir)
    n_touches = loaders.load_touches(client, data_dir)
    n_sessions = loaders.load_sessions(client, data_dir)
    n_materials = loaders.load_materials(client, data_dir)
    n_channels = loaders.load_channels(client, data_dir)
    n_posts = loaders.load_posts(client, data_dir)
    n_todos = loaders.load_todos(client, data_dir)
    n_deals = loaders.load_deals(client, data_dir)
    n_decisions = loaders.load_decisions(client, data_dir)
    n_experiments = loaders.load_experiments(client, data_dir)
    n_events = loaders.load_events(client, data_dir)
    n_routines = loaders.load_routines(client, data_dir)
    t.tln(f"contacts:    rows in file = rows in Aito = {n_contacts}")
    t.tln(f"touches:     rows in file = rows in Aito = {n_touches}")
    t.tln(f"sessions:    rows in file = rows in Aito = {n_sessions}")
    t.tln(f"materials:   rows in file = rows in Aito = {n_materials}")
    t.tln(f"channels:    rows in file = rows in Aito = {n_channels}")
    t.tln(f"posts:       rows in file = rows in Aito = {n_posts}")
    t.tln(f"todos:       rows in file = rows in Aito = {n_todos}")
    t.tln(f"deals:       rows in file = rows in Aito = {n_deals}")
    t.tln(f"decisions:   rows in file = rows in Aito = {n_decisions}")
    t.tln(f"experiments: rows in file = rows in Aito = {n_experiments}")
    t.tln(f"events:      rows in file = rows in Aito = {n_events}")
    t.tln(f"routines:    rows in file = rows in Aito = {n_routines}")

    for table, filename, id_field in (
        ("contacts", loaders.ROLODEX_FILE, "contact_id"),
        ("touches", loaders.TOUCHES_FILE, "touch_id"),
        ("sessions", loaders.SESSIONS_FILE, "session_id"),
        ("materials", loaders.MATERIALS_FILE, "material_id"),
        ("channels", loaders.CHANNELS_FILE, "channel_id"),
        ("posts", loaders.POSTS_FILE, "post_id"),
        ("todos", loaders.TODOS_FILE, "todo_id"),
        ("deals", loaders.DEALS_FILE, "deal_id"),
        ("decisions", loaders.DECISIONS_FILE, "decision_id"),
        ("experiments", loaders.EXPERIMENTS_FILE, "experiment_id"),
        ("events", loaders.EVENTS_FILE, "event_id"),
        ("routines", loaders.ROUTINES_FILE, "routine_id"),
    ):
        t.h2(f"Sample rows: {table}")
        for row_id in _file_ids(data_dir, filename, id_field):
            request = {"from": table, "where": {id_field: row_id}, "limit": 1}
            response = client.query(request)
            t.tln(f"request:  {json.dumps(request, sort_keys=True)}")
            t.tln(f"response: {json.dumps(response['hits'][0], sort_keys=True)}")


def test_load_seed(t: bt.TestCaseRun) -> None:
    t.h1("Loader gate: data/seed")
    _load_and_snapshot(t, SEED_DIR)


def test_load_seed_tiny(t: bt.TestCaseRun) -> None:
    t.h1("Loader gate: data/seed_tiny")
    _load_and_snapshot(t, SEED_TINY_DIR)


def test_malformed_rows_assert(t: bt.TestCaseRun) -> None:
    t.h1("Surprising data raises, never skips (CLAUDE.md rule 3)")
    good_contact = next(
        iter(csv.DictReader(open(SEED_DIR / loaders.ROLODEX_FILE, encoding="utf-8")))
    )
    cases = {
        "unknown segment": {**good_contact, "segment": "blockchain"},
        "missing tier": {**good_contact, "tier": ""},
        "non-boolean phone_present": {**good_contact, "phone_present": "yes"},
    }
    for label, row in cases.items():
        try:
            loaders.parse_rolodex_row(row)
            raise RuntimeError(f"{label}: was accepted, should have raised")
        except AssertionError as e:
            t.tln(f"{label}:")
            t.tln(f"  {e}")

    good_touch = next(
        iter(csv.DictReader(open(SEED_DIR / loaders.TOUCHES_FILE, encoding="utf-8")))
    )
    touch_cases = {
        "unknown outcome": {**good_touch, "outcome": "ghosted"},
        "weekday contradicts ts": {**good_touch, "weekday": "sun"},
        "unknown contact": {**good_touch, "contact_id": "nobody"},
    }
    for label, row in touch_cases.items():
        try:
            loaders.parse_touch_row(row, {good_touch["contact_id"]})
            raise RuntimeError(f"{label}: was accepted, should have raised")
        except AssertionError as e:
            t.tln(f"{label}:")
            t.tln(f"  {e}")
