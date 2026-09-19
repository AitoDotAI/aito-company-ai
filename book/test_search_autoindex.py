"""Auto-refresh (docs/24): the index is a v2 union VIEW, so a source write keeps
search fresh by refreshing the view (log.py calls search.refresh) — the new /
edited item is searchable immediately, a deleted one drops out. No per-row index
to maintain. Requires a running Aito instance.
"""

import booktest as bt

from company_ai import log, loaders, search
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _seed(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)
    search.build_index(client)   # declare the view => refresh keeps it fresh


def _titles(client: AitoClient, query: str) -> list[str]:
    return [h["title"] for h in search.search(client, query, top_n=5).derived["hits"]]


def test_writes_keep_the_view_fresh(t: bt.TestCaseRun) -> None:
    client = _client()
    _seed(client)

    t.h1("A new contact is searchable immediately — the write refreshes the view")
    log.add_contact(client, name="Zyxwq Vartiainen", company="Zyxwq Oy", role="CTO",
                    segment="erp", tier="A", ai_lifecycle="operating", source="cold",
                    country="FI", phone_present=True, email_present=True,
                    notes_tags=["quantum"])
    t.tln(f"search 'Zyxwq': {_titles(client, 'Zyxwq')}")
    assert any("Zyxwq" in x for x in _titles(client, "Zyxwq"))

    t.h1("A new deal is searchable immediately")
    log.add_deal(client, company="Qwptx Ltd", segment="analytics", stage="pilot",
                 value_eur=12345, probability=40, champion_present=True)
    t.tln(f"search 'Qwptx': {_titles(client, 'Qwptx')}")
    assert any("Qwptx" in x for x in _titles(client, "Qwptx"))

    t.h1("A document appears, then drops out when deleted")
    doc = log.add_document(client, title="Jklmn breakthrough", body="A note about jklmn.",
                           kind="internal")
    t.tln(f"after add, search 'Jklmn': {_titles(client, 'Jklmn')}")
    assert any("Jklmn" in x for x in _titles(client, "Jklmn"))
    log.delete_document(client, doc["doc_id"])
    t.tln(f"after delete, search 'Jklmn': {_titles(client, 'Jklmn')}")
    assert not any("Jklmn" in x for x in _titles(client, "Jklmn"))


def test_ensure_index_builds_the_view_when_missing(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)
    client.delete_table("search_items")   # no view yet

    t.h1("A write before the view exists is a no-op (refresh guards on existence)")
    log.add_deal(client, company="Vbnmk Oy", segment="erp", stage="lead",
                 value_eur=1000, probability=10, champion_present=False)
    t.tln(f"view present after write: {'search_items' in client.get_schema()['schema']}")
    assert "search_items" not in client.get_schema()["schema"]

    t.h1("ensure_index then declares the view, whole — including that write")
    search.ensure_index(client)
    t.tln(f"search 'Vbnmk': {_titles(client, 'Vbnmk')}")
    assert any("Vbnmk" in x for x in _titles(client, "Vbnmk"))
