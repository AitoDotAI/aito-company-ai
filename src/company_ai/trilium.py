"""Trilium extractor — bring an existing Trilium note tree into the Documents
store (docs/25, `.ai/tasks/15`). Read-only over Trilium's SQLite
(`notes` + `branches` + `blobs`), converting each note's CKEditor HTML to
markdown and mapping the tree to the documents model:

  <root>/Companies/<Name>   -> a document with company=<Name> (→ company_id link)
  <root>/daily/<YYYY-MM-DD…> -> a document with noted_on = the date in the title

Layout-agnostic beyond those two parents (which the operator names); no personal
subtrees are touched. The output rows feed `log.import_documents` (idempotent on
`source='trilium:<noteId>'`). Content stays out of the repo — this reads a
private DB the operator points at; the repo only carries this generic code and
SYNTHETIC test fixtures.
"""

import html as _html
import re
import sqlite3

_DATE_IN_TITLE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def html_to_md(s: str) -> str:
    """A small CKEditor-HTML → markdown converter (headings, lists, links,
    bold/italic, paragraphs); everything else is stripped. Good enough for
    notes, no dependency."""
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style).*?</\1>", "", s)
    for i in range(1, 7):
        s = re.sub(rf"(?is)<h{i}[^>]*>(.*?)</h{i}>",
                   lambda m, i=i: "\n" + "#" * i + " " + m.group(1).strip() + "\n", s)
    s = re.sub(r"(?is)<li[^>]*>(.*?)</li>", lambda m: "- " + m.group(1).strip() + "\n", s)
    s = re.sub(r"(?is)</?(ul|ol)[^>]*>", "\n", s)
    s = re.sub(r'(?is)<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
               lambda m: f"[{m.group(2).strip()}]({m.group(1)})", s)
    s = re.sub(r"(?is)<(strong|b)[^>]*>(.*?)</\1>", lambda m: "**" + m.group(2).strip() + "**", s)
    s = re.sub(r"(?is)<(em|i)[^>]*>(.*?)</\1>", lambda m: "*" + m.group(2).strip() + "*", s)
    s = re.sub(r"(?is)<br\s*/?>", "\n", s)
    s = re.sub(r"(?is)</p>|</div>|</h[1-6]>", "\n\n", s)
    s = re.sub(r"(?is)<[^>]+>", "", s)          # strip remaining tags
    s = _html.unescape(s).replace("\xa0", " ")   # &nbsp; → space
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _connect(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _child_id(con, parent_id, title):
    r = con.execute(
        "SELECT n.noteId FROM branches b JOIN notes n ON n.noteId=b.noteId "
        "WHERE b.parentNoteId=? AND n.title=? AND b.isDeleted=0 AND n.isDeleted=0 LIMIT 1",
        (parent_id, title)).fetchone()
    return r[0] if r else None


def _children(con, parent_id):
    return con.execute(
        "SELECT n.noteId, n.title, n.blobId, n.type FROM branches b "
        "JOIN notes n ON n.noteId=b.noteId WHERE b.parentNoteId=? "
        "AND b.isDeleted=0 AND n.isDeleted=0 AND n.isProtected=0",
        (parent_id,)).fetchall()


def _body(con, blob_id):
    r = con.execute("SELECT content FROM blobs WHERE blobId=?", (blob_id,)).fetchone()
    raw = r[0] if r and r[0] is not None else ""
    return html_to_md(raw if isinstance(raw, str) else raw.decode("utf-8", "replace"))


def scan_trilium(db_path: str, root: str = "workspace",
                 companies_parent: str = "Companies", daily_parent: str = "daily",
                 min_chars: int = 10) -> list[dict]:
    """Extract document rows from the Trilium DB under `root`. Company notes
    (children of `companies_parent`) → company-linked documents; daily notes
    (children of `daily_parent`, dated by a `YYYY-MM-DD` in the title) → dated
    diary documents. Skips near-empty notes. Rows carry `source='trilium:<id>'`
    for idempotent import."""
    con = _connect(db_path)
    root_row = con.execute(
        "SELECT noteId FROM notes WHERE title=? AND isDeleted=0 LIMIT 1", (root,)).fetchone()
    if not root_row:
        raise ValueError(f"Trilium: no note titled {root!r}")
    root_id = root_row[0]
    rows: list[dict] = []

    comp_id = _child_id(con, root_id, companies_parent)
    for nid, title, blob, typ in (_children(con, comp_id) if comp_id else []):
        if typ != "text":
            continue
        body = _body(con, blob)
        if len(body) < min_chars:
            continue
        rows.append({"title": title.strip(), "body": body, "kind": "internal",
                     "area": None, "company": title.strip(), "stakeholder_id": None,
                     "topics": "customer", "noted_on": None, "source": f"trilium:{nid}"})

    daily_id = _child_id(con, root_id, daily_parent)
    for nid, title, blob, typ in (_children(con, daily_id) if daily_id else []):
        if typ != "text":
            continue
        body = _body(con, blob)
        if len(body) < min_chars:
            continue
        m = _DATE_IN_TITLE.search(title or "")
        rows.append({"title": title.strip(), "body": body, "kind": "internal",
                     "area": None, "company": None, "stakeholder_id": None,
                     "topics": "diary", "noted_on": m.group(1) if m else None,
                     "source": f"trilium:{nid}"})
    return rows


def import_trilium(client, db_path: str, root: str = "workspace") -> dict:
    """Scan a Trilium tree and fold it into the documents store, creating a
    `companies` entity row for any company name not yet present (so every note
    links, not only the ones with an existing contact/deal). Idempotent on the
    `trilium:<noteId>` source — safe to re-run as Trilium grows. Returns the
    `import_documents` report plus `companies_created`."""
    from . import log, schema
    from .loaders import company_slug
    rows = scan_trilium(db_path, root=root)
    existing = {h["company_id"] for h in client.query(
        {"from": "companies", "limit": 1_000_000})["hits"]}
    new: dict[str, str] = {}
    for r in rows:
        if r["company"]:
            cid = company_slug(r["company"])
            if cid not in existing and cid not in new:
                new[cid] = r["company"].strip()
    if new:
        client.upload_batch("companies", [schema.new_company_row(cid, name)
                                          for cid, name in sorted(new.items())])
        client.optimize("companies")
    report = log.import_documents(client, rows)
    report["companies_created"] = len(new)
    return report
