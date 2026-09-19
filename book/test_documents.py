"""Documents — the knowledge store (docs/25).

The store is a first-class Aito collection: this proves the round-trip the UI,
MCP, and search all sit on — seed load, filter by kind/area, a create/edit/
delete that survives Aito, a file import, and (the point of the union) a new
document turning up in smart search as `kind=doc`. Requires a running Aito.

Prints stay date/id-free (live rows are stamped with today's date and a
timestamped id) so the snapshot is stable across runs.
"""

import tempfile
from pathlib import Path

import booktest as bt

from company_ai import documents, loaders, log, search
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _load(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)   # the company_id link target
    loaders.load_rolodex(client, SEED_DIR)     # for the contact link
    loaders.load_documents(client, SEED_DIR)


def _titles(docs) -> list[str]:
    return [d["title"] for d in docs]


def test_seed_feed_and_filters(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)

    t.h1("the seeded store, newest-updated first")
    feed = documents.feed(client).derived
    t.tln(f"count: {feed['count']}")
    for d in feed["documents"]:
        link = f" · {d['company_eff']}" if d["company_eff"] else ""
        link += f" · {d['contact_name']}" if d["contact_name"] else ""
        t.tln(f"  [{d['kind']}/{d['area'] or '—'}] {d['title']}{link}")

    t.h1("filter by kind=docs")
    t.tln(f"  {_titles(documents.feed(client, kind='docs').derived['documents'])}")

    t.h1("filter by area=sales")
    t.tln(f"  {_titles(documents.feed(client, area='sales').derived['documents'])}")

    t.h1("filter by company (effective — the doc's own or its contact's)")
    t.tln(f"  {_titles(documents.feed(client, company='Genco Oy').derived['documents'])}")


def test_entity_link_and_diary_axes(t: bt.TestCaseRun) -> None:
    """Phase 2 (.ai/tasks/15): a document links to the company ENTITY
    (`company_id` → companies), and carries the diary axes — `noted_on` (the day
    the note is about) and free-form `topics`. Pins the link traversal and the
    browse-by-day query the diary rides on."""
    client = _client()
    _load(client)

    t.h1("company_id resolves the entity (documents -> companies)")
    hit = client.query({"from": "documents", "where": {"doc_id": "dc002"},
                        "select": ["title", "company", "company_id", "company_id.name"]})["hits"][0]
    t.tln(f"{hit['title']}: company='{hit['company']}' company_id='{hit['company_id']}' "
          f"-> company_id.name='{hit['company_id.name']}'")
    assert hit["company_id.name"] == hit["company"], "the link resolves to the company name"

    t.h1("the diary axis: browse documents by the day they are about (noted_on)")
    day = client.query({"from": "documents", "where": {"noted_on": "2026-06-14"},
                        "select": ["noted_on", "title", "topics", "company_id.name"]})["hits"]
    for d in day:
        t.tln(f"  {d['noted_on']}  {d['title']}  topics={d.get('topics')}  @ {d.get('company_id.name')}")
    assert len(day) == 1 and day[0]["title"].startswith("Daily note"), "the day's diary entry is found"
    assert day[0]["topics"] == "diary;genco;pilot", "free-form topics are stored and returned"


def test_diary_and_topics_surface(t: bt.TestCaseRun) -> None:
    """Phase 2b (docs/25): the browse-by-day diary and the browse-by-topic index
    over documents — the surface the operator's notes are read through."""
    client = _client()
    _load(client)

    t.h1("diary: documents dated to a day, newest day first, grouped by day")
    d = documents.diary(client).derived
    t.tln(f"diary entries: {d['count']} across {len(d['days'])} day(s)")
    for g in d["days"]:
        for doc in g["documents"]:
            t.tln(f"  {g['day']}  {doc['title']}  @ {doc['company_eff'] or '—'}  "
                  f"topics={doc['topic_list']}")

    t.h1("browse-by-topic index (free-form topics, counted, most-used first)")
    for it in documents.topics(client).derived["topics"]:
        t.tln(f"  {it['topic']}: {it['count']}")

    t.h1("filter the feed by a topic (membership in the ';'-joined axis)")
    t.tln(f"  topic=pilot -> {_titles(documents.feed(client, topic='pilot').derived['documents'])}")

    t.h1("diary narrowed to a company (via the effective-company rollup)")
    dg = documents.diary(client, company="Genco Oy").derived
    t.tln(f"  Genco diary: {[doc['title'] for g in dg['days'] for doc in g['documents']]}")

    all_topics = [it["topic"] for it in documents.topics(client).derived["topics"]]
    assert d["count"] >= 1, "the diary has at least the seeded daily note"
    assert any(doc["title"].startswith("Daily note")
               for g in d["days"] for doc in g["documents"]), "the daily note is in the diary"
    assert "pilot" in all_topics, "free-form topics are indexed"
    assert len(documents.feed(client, topic="pilot").derived["documents"]) == 2, \
        "topic=pilot matches both the account plan and the daily note"


# the legacy journal table's shape — the journal collection is retired from the
# schema (.ai/tasks/15 Phase 2d), so this fixture reconstructs it just enough to
# exercise `migrate_journal`, the one-shot prod converter that still reads the
# instance's journal table by name.
_LEGACY_JOURNAL = {"type": "table", "columns": {
    "entry_id": {"type": "String"}, "date": {"type": "String"},
    "title": {"type": "Text", "analyzer": "english"}, "kind": {"type": "String"},
    "body": {"type": "Text", "analyzer": "english"}, "tags": {"type": "String", "nullable": True},
    "stakeholder_id": {"type": "String", "nullable": True},
    "linked_id": {"type": "String", "nullable": True},
    "linked_type": {"type": "String", "nullable": True},
    "company": {"type": "String", "nullable": True}, "created": {"type": "String"}}}


def test_migrate_journal_into_documents(t: bt.TestCaseRun) -> None:
    """Phase 2d-B (.ai/tasks/15): fold a legacy journal table into documents as
    dated notes — `date` → `noted_on`, `kind`/`tags`/deal-link → `topics`, links
    carried over — so nothing is lost when the journal is retired. Idempotent on
    `source='journal:<entry_id>'`. The journal collection is gone from the schema;
    this rebuilds a tiny one to prove the prod migration path."""
    client = _client()
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)
    client.delete_table("journal")
    client.create_table("journal", _LEGACY_JOURNAL)
    client.upload_batch("journal", [
        {"entry_id": "jn001", "date": "2026-05-01", "title": "Genco meeting", "kind": "meeting",
         "body": "Talked pricing.", "tags": "pricing;follow-up", "stakeholder_id": "sc001",
         "linked_id": "", "linked_type": "", "company": "Genco Oy", "created": "2026-05-01"},
        {"entry_id": "jn002", "date": "2026-05-03", "title": "Idea: onboarding", "kind": "idea",
         "body": "Small experiment.", "tags": "", "stakeholder_id": "",
         "linked_id": "sec003", "linked_type": "deal", "company": "", "created": "2026-05-03"},
        {"entry_id": "jn003", "date": "2026-05-05", "title": "Plain note", "kind": "note",
         "body": "Nothing decided.", "tags": "", "stakeholder_id": "",
         "linked_id": "", "linked_type": "", "company": "", "created": "2026-05-05"},
    ])
    n_journal = client.count("journal")
    docs_before = client.count("documents")
    report = log.migrate_journal(client)
    t.tln(f"journal entries: {n_journal}; migrated: {report['migrated']}, "
          f"replaced: {report['replaced']}")
    t.tln(f"documents: {docs_before} -> {report['documents_total']}")
    assert report["migrated"] == n_journal
    assert report["documents_total"] == docs_before + n_journal

    t.h1("migrated entries: date -> noted_on, kind/tags/deal-link -> topics")
    migrated = [d for d in client.query({"from": "documents", "limit": 2000})["hits"]
                if (d.get("source") or "").startswith("journal:")]
    for d in sorted(migrated, key=lambda x: x["source"]):
        t.tln(f"  {d['noted_on']} [{d['source']}] {d['title']!r} "
              f"topics={d.get('topics')} company={d.get('company')}")
    assert all(d["kind"] == "internal" for d in migrated), "migrated entries are internal notes"
    assert {d["source"] for d in migrated} == {"journal:jn001", "journal:jn002", "journal:jn003"}

    t.h1("re-running is idempotent (replace on source, no duplicates)")
    again = log.migrate_journal(client)
    t.tln(f"second run: +{again['migrated']} migrated, {again['replaced']} replaced, "
          f"{again['documents_total']} total")
    assert again["migrated"] == 0 and again["replaced"] == n_journal
    assert again["documents_total"] == report["documents_total"]


def test_backfill_recovers_company_from_topics(t: bt.TestCaseRun) -> None:
    """td-20260909105919886359: journal-derived documents lost their company link
    at harvest time but kept the company slug in `topics`. The backfill recovers
    it by a literal tag->company_id lookup (rule 2), so the store is browsable by
    account again — leaving genuinely un-attributable notes (no company tag) and
    ambiguous ones (several tags) null, never guessed (rule 3)."""
    client = _client()
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)

    # real seed slugs — the join key is an exact tag == company_id match, so use
    # the actual ids (a topic like "genco" does NOT match company_id "genco-oy")
    comps = {x["company_id"]: x["name"]
             for x in client.query({"from": "companies", "limit": 1000})["hits"]}
    assert len(comps) >= 2, "seed has at least two companies"
    cid0, cid1 = sorted(comps)[:2]
    name0 = comps[cid0]
    # a junk company entity — auto-created, named by its own slug (not a real
    # account). A generic topic token must NOT false-match it (found on prod:
    # an 'overview' tag matched a junk 'overview' company).
    client.upload_batch("companies", [{"company_id": "junkco", "name": "junkco"}])

    # journal-derived-style docs: resolvable / ambiguous / no-company-tag / junk-tag
    a = log.add_document(client, title="Backfill target (jnA)", body="notes", kind="internal",
                         topics=f"call;{cid0};call-outcome", source="journal:jnA")["doc_id"]
    b = log.add_document(client, title="Cross-account sync (jnB)", body="notes", kind="internal",
                         topics=f"diary;{cid0};{cid1}", source="journal:jnB")["doc_id"]
    c = log.add_document(client, title="Week plan (jnC)", body="notes", kind="internal",
                         topics="diary;planning", source="journal:jnC")["doc_id"]
    e = log.add_document(client, title="Overview note (jnE)", body="notes", kind="internal",
                         topics="diary;junkco;overview", source="journal:jnE")["doc_id"]

    def company_of(x):   # null fields are omitted from a v2 projection -> .get;
        h = client.query({"from": "documents", "where": {"doc_id": x}, "limit": 1,
                          "select": ["company"]})["hits"][0]  # and no null link to project
        return h.get("company")
    assert all(company_of(x) is None for x in (a, b, c, e)), "all start unlinked"

    t.h1("dry run: plans the resolvable doc, writes nothing")
    dry = log.backfill_document_companies(client, apply=False)
    t.tln(f"resolved={dry['resolved']} ambiguous={dry['ambiguous']} left_null={dry['left_null']}")
    t.tln(f"planned (ours): {sorted((p['company'], p['title']) for p in dry['planned'] if p['doc_id'] in (a, b, c))}")
    t.tln(f"doc A company after dry run: {company_of(a)!r}")
    assert company_of(a) is None, "dry run must not write"

    t.h1("apply: the resolvable doc gets company + a resolving company_id link")
    log.backfill_document_companies(client, apply=True)
    ra = client.query({"from": "documents", "where": {"doc_id": a}, "limit": 1,
                       "select": ["company", "company_id", "company_id.name"]})["hits"][0]
    t.tln(f"doc A -> company={ra['company']!r} company_id={ra['company_id']!r} link={ra.get('company_id.name')!r}")
    assert ra["company"] == name0 and ra["company_id"] == cid0
    assert ra.get("company_id.name") == name0, "recovered link resolves to the entity"

    t.h1("browsable by account: the by-company feed now finds it")
    titles = [d["title"] for d in documents.feed(client, company=name0).derived["documents"]]
    t.tln(f"feed(company=name0) includes 'Backfill target (jnA)': {'Backfill target (jnA)' in titles}")
    assert "Backfill target (jnA)" in titles

    t.h1("ambiguous, untagged, and junk-company-tag notes stay null, not guessed")
    for x, label in ((b, "ambiguous"), (c, "no-company-tag"), (e, "junk-company-tag")):
        t.tln(f"  {label}: company={company_of(x)!r}")
        assert company_of(x) is None


def test_migrate_journal_recovers_company_from_tags(t: bt.TestCaseRun) -> None:
    """Fix-forward half of td-20260909105919886359: a journal entry whose own
    `company` is null but whose tags carry the company slug must land as a
    document WITH the company set — so the harvest cannot reopen the gap the
    backfill just closed."""
    client = _client()
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)
    comps = {x["company_id"]: x["name"]
             for x in client.query({"from": "companies", "limit": 1000})["hits"]}
    cid0 = sorted(comps)[0]
    name0 = comps[cid0]
    client.delete_table("journal")
    client.create_table("journal", _LEGACY_JOURNAL)
    client.upload_batch("journal", [
        {"entry_id": "jnX", "date": "2026-06-01", "title": "Account sync", "kind": "meeting",
         "body": "notes", "tags": f"{cid0};pricing", "stakeholder_id": "",
         "linked_id": "", "linked_type": "", "company": "", "created": "2026-06-01"}])
    log.migrate_journal(client)
    doc = [d for d in client.query({"from": "documents", "limit": 5000,
           "select": ["source", "company", "company_id", "company_id.name", "topics"]})["hits"]
           if d.get("source") == "journal:jnX"][0]
    t.tln(f"harvested jnX -> company={doc['company']!r} company_id={doc['company_id']!r} "
          f"link={doc.get('company_id.name')!r} topics={doc.get('topics')!r}")
    assert doc["company"] == name0 and doc["company_id"] == cid0
    assert doc.get("company_id.name") == name0, "the harvested link resolves to the entity"


def test_create_edit_delete_round_trip(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    before = documents.feed(client).derived["count"]

    t.h1("create a document (validated like a load: kind/area/contact)")
    row = log.add_document(client, title="Sales opener playbook",
                           body="# Openers\nLead with the churn hook.",
                           kind="internal", area="sales", company="Genco Oy",
                           stakeholder_id="sc001")
    doc_id = row["doc_id"]
    got = documents.read(client, doc_id)
    t.tln(f"created: [{got['kind']}/{got['area']}] {got['title']} "
          f"· {got['company_eff']} · {got['contact_name']}")
    t.tln(f"count now: {documents.feed(client).derived['count']} (was {before})")

    t.h1("edit it (retag docs, drop the area) — the full-rewrite path, no _modify")
    log.update_document(client, doc_id, {"kind": "docs", "area": ""})
    ed = documents.read(client, doc_id)
    t.tln(f"after edit: kind={ed['kind']} area={ed['area']}")

    t.h1("a dangling contact link is refused (rule 3)")
    try:
        log.add_document(client, title="Bad", body="x", stakeholder_id="nope")
    except AssertionError as e:
        t.tln(f"  refused: {e}")

    t.h1("delete it")
    log.delete_document(client, doc_id)
    t.tln(f"count back to: {documents.feed(client).derived['count']}")


def test_document_shows_up_in_smart_search(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)

    t.h1("a new document is searchable as kind=doc (the union, docs/23)")
    log.add_document(client, title="Churn prediction playbook",
                     body="# Churn\nRank accounts by predicted churn, then reach the top.",
                     kind="internal", area="sales")
    search.build_index(client)
    hits = search.search(client, "churn playbook", kind="doc").derived["hits"]
    t.tln("doc hits for 'churn playbook':")
    for h in hits[:5]:
        t.tln(f"  {h['title']}")
    assert any("Churn prediction playbook" == h["title"] for h in hits)


def test_import_a_markdown_dir(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    scratch = Path(tempfile.mkdtemp(prefix="docimport-"))
    (scratch / "gtm.md").write_text(
        "---\nkind: internal\narea: sales\ncompany: Wonka Oy\n---\n"
        "# GTM plan\nWedge into Nordic ERP shops.\n", encoding="utf-8")
    (scratch / "readme.md").write_text("# Readme\nHow this repo works.\n", encoding="utf-8")

    t.h1("import a markdown dir (front-matter → tags; first heading → title)")
    rows = documents.scan_dir(scratch)
    report = log.import_documents(client, rows)
    t.tln(f"first import: +{report['added']} new, {report['replaced']} replaced")
    imported = [d for d in documents.feed(client).derived["documents"] if d.get("source")]
    for d in sorted(imported, key=lambda x: x["source"]):
        t.tln(f"  {d['source']} -> [{d['kind']}/{d['area'] or '—'}] {d['title']}"
              f"{(' · ' + d['company_eff']) if d['company_eff'] else ''}")

    t.h1("re-import is idempotent on the file path (source), not duplicated")
    report2 = log.import_documents(client, documents.scan_dir(scratch))
    t.tln(f"second import: +{report2['added']} new, {report2['replaced']} replaced")


def test_import_diary_and_topics(t: bt.TestCaseRun) -> None:
    """Phase 2c (docs/25): the importer is Phase-2-aware. `noted_on` comes from
    front-matter OR an unambiguous YYYY-MM-DD in the filename (a Trilium daily
    note), `topics` from a comma/semicolon front-matter list, and `company_id` is
    derived — so an imported note files itself into the diary and hangs off the
    company entity, layout-agnostically (no folder-name guessing)."""
    client = _client()
    _load(client)
    scratch = Path(tempfile.mkdtemp(prefix="trilium-"))
    # a daily note: date in the FILENAME, no explicit noted_on
    (scratch / "2026-06-15-genco-sync.md").write_text(
        "---\ncompany: Genco Oy\nstakeholder: sc001\ntopics: pilot, standup\n---\n"
        "# Genco sync\nWalked through the invoicing export; pilot scope agreed.\n",
        encoding="utf-8")
    # a durable topic note: explicit front-matter, no date anywhere
    (scratch / "positioning.md").write_text(
        "---\nkind: docs\ntopics: positioning;messaging\n---\n"
        "# Positioning\nPredictive DB, not another dashboard.\n", encoding="utf-8")

    rows = log.import_documents(client, documents.scan_dir(scratch))
    t.tln(f"imported: +{rows['added']} new, {rows['replaced']} replaced")

    t.h1("the daily note landed in the diary (noted_on from the filename)")
    imported = {d["source"]: d for d in documents.feed(client).derived["documents"] if d.get("source")}
    daily = imported["2026-06-15-genco-sync.md"]
    t.tln(f"  {daily['title']}: noted_on={daily['noted_on']} company_id={daily['company_id']} "
          f"topics={daily['topic_list']}")
    assert daily["noted_on"] == "2026-06-15", "noted_on inferred from the filename date"
    assert daily["company_id"] == "genco-oy", "company_id derived from the company"
    assert daily["topic_list"] == ["pilot", "standup"], "front-matter topics parsed"

    t.h1("the durable note has topics but no diary date")
    durable = imported["positioning.md"]
    t.tln(f"  {durable['title']}: noted_on={durable['noted_on']} topics={durable['topic_list']}")
    assert durable["noted_on"] is None, "no date anywhere -> not a diary entry"
    assert durable["topic_list"] == ["messaging", "positioning"] or \
        set(durable["topic_list"]) == {"positioning", "messaging"}, "semicolon topics parsed"

    t.h1("the imported daily note shows up in the diary surface")
    diary_titles = [doc["title"] for g in documents.diary(client).derived["days"]
                    for doc in g["documents"]]
    t.tln(f"  diary now: {sorted(diary_titles)}")
    assert "Genco sync" in diary_titles, "the imported daily note is browsable by day"
