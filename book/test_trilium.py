"""Trilium extractor (docs/25, .ai/tasks/15): the operator's Trilium note tree
folds into the documents store — company notes link to the company entity, daily
notes become dated diary documents. The fixture is a SYNTHETIC Trilium SQLite
built in-test (no real note data in the repo). The import needs a running Aito.
"""

import sqlite3
import tempfile
from pathlib import Path

import booktest as bt

from company_ai import documents, loaders, trilium
from company_ai.aito import AitoClient
from company_ai.config import Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _synthetic_trilium() -> str:
    """A tiny Trilium DB: workspace/Companies/{Acme Oy, Globex} + workspace/daily/<dated>."""
    path = str(Path(tempfile.mkdtemp(prefix="trilium-")) / "document.db")
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE notes (noteId TEXT, title TEXT, type TEXT, isDeleted INT,"
        " isProtected INT, blobId TEXT);"
        "CREATE TABLE branches (noteId TEXT, parentNoteId TEXT, isDeleted INT);"
        "CREATE TABLE blobs (blobId TEXT, content TEXT);")

    def add(nid, title, parent, html=""):
        con.execute("INSERT INTO notes VALUES (?,?,?,0,0,?)", (nid, title, "text", f"b_{nid}"))
        con.execute("INSERT INTO branches VALUES (?,?,0)", (nid, parent))
        con.execute("INSERT INTO blobs VALUES (?,?)", (f"b_{nid}", html))

    add("e", "workspace", "root")
    add("co", "Companies", "e")
    add("da", "daily", "e")
    add("c1", "Acme Oy", "co",
        '<div class="ck-content"><h2>Acme</h2><p>Met their <strong>CTO</strong>.</p>'
        '<ul><li>pilot on invoices</li><li>see <a href="https://acme.example">site</a></li></ul></div>')
    add("c2", "Globex", "co", "<p>Cold outreach&nbsp;— no reply yet.</p>")
    add("day1", "2026-06-14 kickoff", "da", "<p>Kickoff notes for the day.</p>")
    con.commit()
    con.close()
    return path


def test_html_to_md(t: bt.TestCaseRun) -> None:
    t.h1("CKEditor HTML → markdown")
    md = trilium.html_to_md(
        '<h2>Title</h2><p>A <strong>bold</strong> and <em>italic</em> line.</p>'
        '<ul><li>one</li><li><a href="https://x.example">link</a></li></ul>')
    t.tln(md)
    assert "## Title" in md and "**bold**" in md and "*italic*" in md
    assert "- one" in md and "[link](https://x.example)" in md


def test_scan_extracts_companies_and_diary(t: bt.TestCaseRun) -> None:
    db = _synthetic_trilium()
    rows = trilium.scan_trilium(db)
    t.h1("scan: company notes + a dated daily note")
    for r in sorted(rows, key=lambda x: x["source"]):
        t.tln(f"  [{r['topics']}] {r['title']!r} company={r['company']} "
              f"noted_on={r['noted_on']} source={r['source']}")
        t.tln(f"      body: {r['body'][:80]!r}")
    company = [r for r in rows if r["topics"] == "customer"]
    daily = [r for r in rows if r["topics"] == "diary"]
    assert {r["company"] for r in company} == {"Acme Oy", "Globex"}
    assert daily and daily[0]["noted_on"] == "2026-06-14", "date parsed from the daily title"
    assert "**CTO**" in next(r["body"] for r in company if r["company"] == "Acme Oy")


def test_import_links_notes_to_the_company_entity(t: bt.TestCaseRun) -> None:
    """import_trilium creates a company entity for a new name and links the note
    to it — so a Trilium note hangs off the same node as its Aito contacts."""
    client = _client()
    loaders.create_schema(client)
    loaders.clear_table(client, "companies")
    loaders.clear_table(client, "documents")
    db = _synthetic_trilium()

    report = trilium.import_trilium(client, db)
    t.h1("import: new companies created + notes filed as documents")
    t.tln(f"companies_created={report['companies_created']} added={report['added']} "
          f"total={report['total']}")

    hit = client.query({"from": "documents", "where": {"company": "Acme Oy"},
                        "select": ["title", "company", "company_id", "company_id.name",
                                   "topics", "source"]})["hits"][0]
    t.tln(f"Acme note: company_id={hit.get('company_id')} -> {hit.get('company_id.name')} "
          f"topics={hit.get('topics')} source={hit.get('source')}")
    assert hit["company_id.name"] == "Acme Oy", "the note links to the created company entity"
    assert hit["source"] == next(r["source"] for r in trilium.scan_trilium(db)
                                 if r["company"] == "Acme Oy")

    diary = documents.diary(client).derived
    t.tln(f"diary: {diary['count']} dated entries; days={[d['day'] for d in diary['days']]}")
    assert any(d["day"] == "2026-06-14" for d in diary["days"]), "the daily note is in the diary"

    t.h1("re-import is idempotent on the trilium source")
    again = trilium.import_trilium(client, db)
    t.tln(f"second run: added={again['added']} replaced={again['replaced']} "
          f"companies_created={again['companies_created']}")
    assert again["added"] == 0 and again["companies_created"] == 0
