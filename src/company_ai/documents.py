"""Documents — the knowledge store (docs/25).

A read surface over the `documents` collection (the write path is in log.py, a
full-table rewrite, never `_modify`). Lists documents with optional filters
(kind / area / company / person / topic), joining the linked contact in for display.
Plus a path-safe file *importer* so an existing markdown knowledge dir (the old
`COMPANY_AI_LIBRARY_DIR`) can move into the store once.

No prediction here (rule 2): documents are content. The only ranking over them
is Aito's text-`_match` in smart search (docs/23).
"""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import schema
from .aito import AitoClient

_DATE_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


class DocumentError(RuntimeError):
    pass


@dataclass
class Result:
    calls: list = field(default_factory=list)
    derived: dict | None = None


def split_topics(value: str | None) -> list[str]:
    """The ';'-joined free-form topics field → a clean list (docs/25, Phase 2)."""
    return [t.strip() for t in (value or "").split(";") if t.strip()]


def feed(client: AitoClient, limit: int = 500, kind: str | None = None,
         area: str | None = None, company: str | None = None,
         contact: str | None = None, topic: str | None = None) -> Result:
    """Documents, newest-updated first. Filters (kind / area / company / person /
    topic) narrow it. The linked contact's name + company are joined in for
    display, and an *effective* company (the doc's own `company`, else the linked
    contact's) is exposed so an area/company rollup stays consistent. `topic`
    matches membership in the free-form `topics` axis."""
    if kind is not None:
        assert kind in schema.DOC_KINDS, f"unknown kind {kind!r}; have {sorted(schema.DOC_KINDS)}"
    if area is not None:
        assert area in schema.DOCUMENT_AREAS, \
            f"unknown area {area!r}; have {sorted(schema.DOCUMENT_AREAS)}"
    result = Result()
    where = {}
    if kind:
        where["kind"] = kind
    if area:
        where["area"] = area
    if contact:
        where["stakeholder_id"] = contact
    request = {"from": "documents", "limit": limit}
    if where:
        request["where"] = where
    response = client.query(request)
    result.calls.append(("_query", request, response))

    contacts = client.query({"from": "contacts", "limit": 100000})["hits"]
    by_id = {c["contact_id"]: c for c in contacts}

    docs = []
    for r in response["hits"]:
        c = by_id.get(r.get("stakeholder_id"))
        company_eff = r.get("company") or (c["company"] if c else None)
        if company and company_eff != company:
            continue
        topic_list = split_topics(r.get("topics"))
        if topic and topic not in topic_list:
            continue
        # Aito omits absent nullable keys — normalise so the shape is always
        # complete (the UI/MCP/booktest read these directly).
        docs.append({
            **r,
            "area": r.get("area"), "company": r.get("company"),
            "company_id": r.get("company_id"),
            "topics": r.get("topics"), "topic_list": topic_list,
            "noted_on": r.get("noted_on"),
            "stakeholder_id": r.get("stakeholder_id"), "source": r.get("source"),
            "contact_name": c["name"] if c else None,
            "contact_company": c["company"] if c else None,
            "company_eff": company_eff,
        })
    docs.sort(key=lambda d: (d.get("updated") or "", d.get("created") or "", d["doc_id"]),
              reverse=True)
    result.derived = {"count": len(docs), "documents": docs}
    return result


def diary(client: AitoClient, company: str | None = None, topic: str | None = None,
          since: str | None = None, until: str | None = None, limit: int = 500) -> Result:
    """The diary: documents dated to a day (`noted_on` set), newest day first and
    grouped by day — the browse-by-day surface (docs/25, Phase 2). Optionally
    narrowed to a company, a topic, or an ISO `[since, until]` window. Pure
    filtering + grouping over `feed` (rule 2: no ranking, ISO dates sort as text)."""
    inner = feed(client, limit=limit, company=company, topic=topic)
    dated = [d for d in inner.derived["documents"] if d.get("noted_on")]
    if since:
        dated = [d for d in dated if d["noted_on"] >= since]
    if until:
        dated = [d for d in dated if d["noted_on"] <= until]
    dated.sort(key=lambda d: (d["noted_on"], d["doc_id"]), reverse=True)
    by_day: dict[str, list] = {}
    for d in dated:
        by_day.setdefault(d["noted_on"], []).append(d)
    days = [{"day": day, "documents": by_day[day]} for day in sorted(by_day, reverse=True)]
    result = Result(calls=list(inner.calls))
    result.derived = {"count": len(dated), "days": days, "documents": dated}
    return result


def topics(client: AitoClient, limit: int = 2000) -> Result:
    """The distinct topics across the store, each with its document count — the
    browse-by-topic index over the free-form axis (docs/25, Phase 2). Split from
    the ';'-joined field and counted (formatting, not inference)."""
    inner = feed(client, limit=limit)
    counts: dict[str, int] = {}
    for d in inner.derived["documents"]:
        for tp in d.get("topic_list") or []:
            counts[tp] = counts.get(tp, 0) + 1
    items = [{"topic": tp, "count": n}
             for tp, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    result = Result(calls=list(inner.calls))
    result.derived = {"count": len(items), "topics": items}
    return result


def read(client: AitoClient, doc_id: str) -> dict:
    """One document by id, with the same display joins as `feed`."""
    hits = client.query({"from": "documents", "where": {"doc_id": doc_id}, "limit": 1})["hits"]
    if not hits:
        raise DocumentError(f"no such document: {doc_id!r}")
    r = hits[0]
    c = None
    if r.get("stakeholder_id"):
        cs = client.query({"from": "contacts",
                           "where": {"contact_id": r["stakeholder_id"]}, "limit": 1})["hits"]
        c = cs[0] if cs else None
    return {**r, "area": r.get("area"), "company": r.get("company"),
            "company_id": r.get("company_id"),
            "topics": r.get("topics"), "topic_list": split_topics(r.get("topics")),
            "noted_on": r.get("noted_on"),
            "stakeholder_id": r.get("stakeholder_id"), "source": r.get("source"),
            "contact_name": c["name"] if c else None,
            "contact_company": c["company"] if c else None,
            "company_eff": r.get("company") or (c["company"] if c else None)}


# ---- file import (one-time bulk load of an existing markdown dir) ----

def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _front_matter(text: str) -> tuple[dict, str]:
    """Parse an optional leading `--- ... ---` YAML-ish block of flat
    `key: value` lines (kind/area/company/stakeholder). Returns (meta, body)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta, i = {}, 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
        i += 1
    body = "\n".join(lines[i + 1:]) if i < len(lines) else ""
    return meta, body


def _join_topics(raw: str | None) -> str | None:
    """Front-matter `topics` (comma- or semicolon-separated) → the store's
    ';'-joined encoding. None when empty."""
    parts = [p.strip() for p in re.split(r"[;,]", raw or "") if p.strip()]
    return ";".join(parts) or None


def _noted_on(meta: dict, rel: str, stem: str) -> str | None:
    """The day a note is about: an explicit front-matter `noted_on` wins;
    otherwise an unambiguous `YYYY-MM-DD` in the filename (a Trilium daily note
    exports as e.g. `2026-06-14.md`). Layout-agnostic — no folder-name guessing.
    A malformed explicit date raises (rule 3)."""
    explicit = (meta.get("noted_on") or "").strip()
    if explicit:
        try:
            date.fromisoformat(explicit)
        except ValueError as exc:
            raise DocumentError(f"{rel}: bad noted_on {explicit!r} (want YYYY-MM-DD)") from exc
        return explicit
    m = _DATE_IN_NAME.search(stem)
    return m.group(1) if m else None


def scan_dir(root: Path) -> list[dict]:
    """Walk markdown under `root` (path-safe: no traversal, `.md` only) into
    parseable document rows. Title = first `# heading` (else filename); `source`
    = the relative path (import is idempotent on it). Front-matter carries
    kind/area/company/stakeholder and the Phase-2 axes `topics` (comma/semicolon
    list) and `noted_on`; `noted_on` also falls back to a `YYYY-MM-DD` in the
    filename, so a Trilium daily-note export lands in the diary without editing.
    Content stays out of the repo — this reads a private dir the operator points
    at, it does not commit anything."""
    root = root.resolve()
    if not root.exists():
        raise DocumentError(f"no such directory: {root}")
    rows = []
    for path in sorted(root.rglob("*.md")):
        rel = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8")
        meta, body = _front_matter(text)
        kind = meta.get("kind", "internal")
        assert kind in schema.DOC_KINDS, f"{rel}: unknown kind {kind!r}"
        area = meta.get("area") or None
        assert area is None or area in schema.DOCUMENT_AREAS, f"{rel}: unknown area {area!r}"
        rows.append({
            "title": _title(body or text, path.stem),
            "body": body or text,
            "kind": kind,
            "area": area,
            "company": meta.get("company") or None,
            "stakeholder_id": meta.get("stakeholder") or None,
            "topics": _join_topics(meta.get("topics")),
            "noted_on": _noted_on(meta, rel, path.stem),
            "source": rel,
        })
    return rows
