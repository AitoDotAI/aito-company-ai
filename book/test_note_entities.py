"""New company / new person from the note editor (log.add_company + the contact
endpoint's ensure-company path).

The note editor's "＋ New" buttons create entities live, after the initial load.
A company entity is the link target that documents and contacts point at via
`company_id`; `load_companies` guarantees no dangling link at load time by
scanning every source, and this proves the live-write equivalent: adding a
company that first appears now, idempotently, so a document (and a contact) that
names it resolves the link instead of dangling. Requires a running Aito.

Prints stay id/date-free so the snapshot is stable across runs.
"""

import booktest as bt

from company_ai import loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _company_ids(client: AitoClient) -> set[str]:
    return {c["company_id"] for c in
            client.query({"from": "companies", "limit": 100000})["hits"]}


def test_add_company_idempotent_and_links(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_rolodex(client, SEED_DIR)

    before = _company_ids(client)
    assert "novaco" not in before, "fixture assumption: NovaCo is not in the seed"

    t.h1("add a brand-new company")
    created = log.add_company(client, "NovaCo")
    t.tln(f"company_id={created['company_id']}  name={created['name']}  created={created['created']}")
    assert created == {"company_id": "novaco", "name": "NovaCo", "created": True}
    assert "novaco" in _company_ids(client)

    t.h1("adding it again is idempotent (safe to press twice)")
    again = log.add_company(client, "NovaCo")
    t.tln(f"created={again['created']}  count_unchanged={len(_company_ids(client)) == len(before) + 1}")
    assert again["created"] is False
    assert len(_company_ids(client)) == len(before) + 1

    t.h1("the slug folds case, so a different-cased spelling hits the same row")
    same = log.add_company(client, "NOVACO")
    t.tln(f"'NOVACO' -> {same['company_id']}  created={same['created']}")
    assert same["company_id"] == "novaco" and same["created"] is False

    t.h1("a document naming the new company resolves its company_id link")
    log.add_document(client, title="NovaCo intro call", body="# Notes\nfirst call",
                     kind="internal", company="NovaCo")
    hits = client.query({
        "from": "documents",
        "where": {"title": "NovaCo intro call"},
        "select": ["title", "company", "company_id.name"],
        "limit": 1,
    })["hits"]
    linked = hits[0].get("company_id.name")
    t.tln(f"doc.company={hits[0]['company']!r}  ->  company_id.name={linked!r}")
    assert linked == "NovaCo", "the link must resolve to the entity, not dangle"


def test_contact_endpoint_ensures_company(t: bt.TestCaseRun) -> None:
    """The /api/contacts path does add_company(ensure) then add_contact, so a
    person added at a company that has no entity row yet still links cleanly."""
    client = _client()
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_rolodex(client, SEED_DIR)

    assert "orbitworks" not in _company_ids(client)

    t.h1("ensure-then-add: the endpoint's two-step for a person at a new company")
    log.add_company(client, "OrbitWorks")          # what contacts_create does first
    contact = log.add_contact(
        client, name="Dana Fox", company="OrbitWorks", role="CTO",
        segment="other", tier="C", ai_lifecycle="none", source="cold",
        country="Finland", phone_present=False, email_present=True)
    t.tln(f"contact company={contact['company']!r}  company_id={contact['company_id']!r}")
    assert contact["company_id"] == "orbitworks"

    hits = client.query({
        "from": "contacts",
        "where": {"contact_id": contact["contact_id"]},
        "select": ["name", "company_id.name"],
        "limit": 1,
    })["hits"]
    t.tln(f"contact.company_id.name={hits[0].get('company_id.name')!r}")
    assert hits[0].get("company_id.name") == "OrbitWorks"
