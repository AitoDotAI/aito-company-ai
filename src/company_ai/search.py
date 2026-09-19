"""Smart search over content — a unified index the assistant grounds on (RAG).

`search_items` is a denormalized index built by fanning out over the other
tables (docs, contacts, deals). `search()` ranks it by Aito text-`_match`
over the analyzed title/text — the ranking is an Aito query, not a Python
heuristic (rule 2). The model (assistant/agent) picks the query and narrates the
hits; it never computes the ranking.

This is the read half. The impressions/click learning loop (server-side
impression logging, clicks via dashboard + MCP, then an impressions-trained
ranking) is the parked second step — docs/23, `.ai/tasks/09`.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import zip_longest

from . import schema
from .aito import AitoClient

# Unicode word characters (minus underscore) so accented and non-Latin query
# terms survive tokenization — an ASCII-only class treats ä ö å ü ß … as
# delimiters and shreds Finnish/Swedish/German words into single-char fragments
# before Aito ever sees them (docs/23, .ai/tasks/13).
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Result:
    calls: list = field(default_factory=list)
    derived: dict | None = None


# --- the index is a v2 union VIEW (docs/23, docs/24). `search_items` merges the
# source collections behind one searchable `content` column — no materialised
# copy to maintain, no per-row writes (so the `_modify` bugs never touch it). It
# is refreshed, not mutated. Documents are a real collection (docs/25), so they
# union directly like the other sources — no staging table.

# each branch projects the same columns; `content` is a $text merge Aito can
# full-text-search, `title` a readable single-column $text, `kind` a literal.
# `$text` only merges Text columns, and every branch must agree on a column's
# type — so contacts/deals feed it their derived `search_*` Text copies while
# their identifying fields stay categorical String for prediction (docs/23).
_VIEW = {"type": "view", "as": {"union": [
    {"from": "contacts", "select": {"kind": {"$const": "contact"}, "source_id": "contact_id",
        "title": {"$text": ["search_title"]},
        "content": {"$text": ["search_text"]}}},
    {"from": "deals", "select": {"kind": {"$const": "deal"}, "source_id": "deal_id",
        "title": {"$text": ["search_title"]},
        "content": {"$text": ["search_text"]}}},
    {"from": "documents", "select": {"kind": {"$const": "doc"}, "source_id": "doc_id",
        "title": {"$text": ["title"]}, "content": {"$text": ["title", "body"]}}},
]}}


def _view_exists(client: AitoClient) -> bool:
    return "search_items" in client.get_schema()["schema"]


def ensure_index(client: AitoClient) -> dict | None:
    """Build the view if it's missing; otherwise leave it. Called before serving
    a search so a fresh instance searches something."""
    if not _view_exists(client):
        return build_index(client)
    return None


def build_index(client: AitoClient, embed=None) -> dict:
    """(Re)declare `search_items` as the union view over the sources. Documents
    are a real collection now (docs/25), so they union directly — no staging
    table. The view materialises on create; there is no per-row index to keep in
    sync (docs/24).

    When an `embed` callable is given (Azure embeddings, embed.embedder), also
    (re)build `search_vectors` — one embedding per item — for semantic /
    cross-lingual retrieval. This is the ONE place items are embedded: at reindex,
    not on every write. Without `embed`, vectors are skipped and search stays pure
    text-match."""
    client.ensure_table("documents", schema.DOCUMENTS)  # a fresh instance may lack it
    client.delete_table("search_items")
    client.create_view("search_items", _VIEW)
    client.refresh_view("search_items")
    stats = {"indexed": client.count("search_items"), "by_kind": _by_kind(client)}
    if embed is not None:
        stats["vectors"] = build_vectors(client, embed)
    return stats


def build_vectors(client: AitoClient, embed) -> int:
    """Embed every `search_items` row into `search_vectors` (item_id, kind, vec).
    Reads the view's content, embeds it in batches (embed handles batching), and
    rewrites the collection wholesale — an index, rebuilt not mutated, like the
    view. Returns the number of vectors written. Aito owns all vector ranking
    (rule 2); this only featurizes."""
    rows = client.query({"from": "search_items", "limit": 100000,
                         "select": ["kind", "source_id", "title", "content"]})["hits"]
    client.delete_table("search_vectors")
    if not rows:
        return 0
    client.create_table("search_vectors", schema.SEARCH_VECTORS)
    vecs = embed([r.get("content") or r.get("title") or r.get("kind", "") for r in rows])
    payload = [
        {"item_id": f"{r['kind']}:{r['source_id']}", "kind": r["kind"],
         "source_id": r["source_id"], "title": r.get("title"), "vec": v}
        for r, v in zip(rows, vecs)]
    # upload in small chunks: a full-corpus batch of 3072-dim vectors exceeds
    # Aito's request-size limit (a one-shot POST 500s "Request too large").
    for i in range(0, len(payload), 32):
        client.upload_batch("search_vectors", payload[i:i + 32])
    return client.count("search_vectors")


def _vector_candidates(client: AitoClient, embed, query: str, kind: str | None,
                       n: int) -> list[dict]:
    """Retrieve by embedding similarity: embed the query, `$nearest` over
    `search_vectors` (cosine), most similar first. Returns [{item_id, $similarity}]
    or [] if the vector index isn't built yet (never reindexed with embeddings) —
    a missing index degrades to text-match, it does not raise. `kind` is
    post-filtered (item_id carries it) so a kind query needn't special-case the
    `$nearest` predicate."""
    if not _vectors_ready(client):
        return []
    try:
        qvec = embed([query])[0]
    except Exception:
        # a transient embeddings failure (outage, rate-limit, bad key) degrades to
        # text-match — it must not take the whole search endpoint down (docs/23).
        return []
    request = {"from": "search_vectors",
               "where": {"$nearest": {"near": {"vec": qvec}, "limit": max(n * 3, 30)}},
               "select": ["item_id", "kind", "source_id", "title", "$similarity"],
               "limit": max(n * 3, 30)}
    hits = client.query(request)["hits"]
    if kind:
        hits = [h for h in hits if h.get("kind") == kind]
    return hits[:n]


def _vectors_ready(client: AitoClient) -> bool:
    try:
        return "search_vectors" in client.get_schema()["schema"]
    except Exception:
        return False


def _by_kind(client: AitoClient) -> dict:
    return {k: client.query({"from": "search_items", "where": {"kind": k}, "limit": 0})["total"]
            for k in sorted(schema.SEARCH_KINDS)}


def refresh(client: AitoClient) -> None:
    """Re-materialise the view from its (changed) sources. Cheap and idempotent;
    a no-op if the view isn't built yet. Replaces the old per-row auto-reindex —
    a source write just refreshes the view (docs/24)."""
    if _view_exists(client):
        client.refresh_view("search_items")


def _match_clause(query: str) -> dict | None:
    """Aito text-match over title + text for any query token. `$match` is AND
    within a single string (a whole natural-language query matches almost
    nothing), so we tokenize and OR the terms: an item matches if it contains
    any term, and `search()` ranks the matches by Aito relevance (`$similarity`).
    Aito does the matching and the ranking — Python only splits the string
    (rule 2). Returns None when the query has no searchable terms."""
    terms = _TOKEN.findall(query.lower())[:12]
    if not terms:
        return None
    return {"$or": [{"content": {"$match": term}} for term in terms]}


def search(client: AitoClient, query: str, kind: str | None = None,
           top_n: int = 10) -> Result:
    """Rank view items by Aito text-`_match` over the merged `content`, most
    relevant first. `where` keeps only items that match a query term; `orderBy
    {$similarity}` ranks those by Aito's relevance of the content to the query —
    the relevance is Aito's, never a Python heuristic. Optionally restrict to one
    kind. `item_id` is derived (`kind:source_id`) — the view has no such column.

    A non-empty query that yields no searchable terms (e.g. punctuation only)
    matches nothing and returns an empty result — a query of symbols is not
    surprising *data* (rule 3), so it must not 500 the search endpoint."""
    assert query and query.strip(), "search query must not be empty"
    if kind is not None:
        assert kind in schema.SEARCH_KINDS, f"unknown search kind {kind!r}"
    result = Result()

    clause = _match_clause(query)
    if clause is None:
        result.derived = {"query": query, "kind": kind, "count": 0, "hits": []}
        return result
    where = {"$and": [{"kind": kind}, clause]} if kind else clause
    request = {"from": "search_items", "where": where,
               "orderBy": {"$similarity": {"content": query}},
               "limit": top_n, "select": ["kind", "source_id", "title"]}
    response = client.query(request)
    result.calls.append(("_query", request, response))

    hits = [{
        "item_id": f"{h['kind']}:{h['source_id']}", "kind": h["kind"],
        "source_id": h["source_id"], "title": h["title"], "tags": None,
    } for h in response["hits"]]
    result.derived = {"query": query, "kind": kind, "count": len(hits), "hits": hits}
    return result


# --- the impressions loop (docs/23, A+C). Serving a search logs a context + one
# impression per hit (server-side telemetry, not an assistant write); a click
# flips its impression. The learned ranking reads these back. ---

def _impressions_ready(client: AitoClient) -> None:
    client.ensure_table("search_contexts", schema.SEARCH_CONTEXTS)
    client.ensure_table("search_impressions", schema.SEARCH_IMPRESSIONS)


def _log_impressions(client: AitoClient, query: str, hits: list[dict],
                     source: str, anchor_item_id: str | None) -> str:
    """Record the context and one impression per shown hit; return context_id."""
    _impressions_ready(client)
    at = _now()
    context_id = "ctx_" + uuid.uuid4().hex[:12]
    client.upload_batch("search_contexts", [{
        "context_id": context_id, "query": query,
        "anchor_item_id": anchor_item_id or None, "source": source, "at": at,
    }])
    rows = [{
        "impression_id": "imp_" + uuid.uuid4().hex[:12],
        "context_id": context_id, "query": query, "item_id": h["item_id"],
        "position": i, "clicked": False, "at": at,
    } for i, h in enumerate(hits)]
    if rows:
        client.upload_batch("search_impressions", rows)
    return context_id


def _ctx_match(query: str) -> dict | None:
    """Match past impressions whose (denormalised) query shares a term with this
    one — the evidence the learned ranking conditions on. Reads the impression's
    own `query` field, no link (docs/24)."""
    terms = _TOKEN.findall(query.lower())[:12]
    if not terms:
        return None
    return {"$or": [{"query": {"$match": term}} for term in terms]}


def ranked(client: AitoClient, query: str, kind: str | None = None,
           top_n: int = 10, embed=None) -> Result:
    """The blended ranking. Three Aito signals, merged (never scored) in Python:

      1. **text-match** — `$match` retrieves candidates; works cold, exact.
      2. **semantic** — when `embed` is given (embeddings configured) and the
         vector index is built, `$nearest` over `search_vectors` adds candidates
         by cosine — including items that share *no tokens* with the query (a
         French query over English docs, a paraphrase). This is the vector-first
         signal.
      3. **learned** — once clicks exist, `_recommend` reorders by P(click) for a
         query like this.

    Python only MERGES the orderings by priority (learned, then vector, then
    text) — it computes no score (rule 2). Every signal degrades gracefully: no
    vectors → text-match; no clicks → vector+text; neither → the old text-match."""
    result = Result()
    base = search(client, query, kind=kind, top_n=max(top_n * 4, 50))
    result.calls.extend(base.calls)
    text_hits = base.derived["hits"]
    text_rank = {h["item_id"]: i for i, h in enumerate(text_hits)}
    by_id = {h["item_id"]: h for h in text_hits}

    # semantic candidates — may include items text-match never found (the point)
    vec_rank: dict[str, int] = {}
    if embed is not None:
        vhits = _vector_candidates(client, embed, query, kind, max(top_n * 4, 50))
        if vhits:
            result.calls.append(("_query", {"$nearest": "search_vectors"}, {"hits": len(vhits)}))
        for i, h in enumerate(vhits):
            vec_rank[h["item_id"]] = i
            by_id.setdefault(h["item_id"], {
                "item_id": h["item_id"], "kind": h["kind"],
                "source_id": h.get("source_id"), "title": h.get("title"), "tags": None})

    candidates = list(by_id.values())
    learned_pos: dict[str, int] = {}
    ctx = _ctx_match(query)
    # Activate the learned re-rank ONLY once a real click exists for a query like
    # this one — NOT on impressions. Impressions are logged automatically on every
    # search (server-side telemetry); gating on their count fires `_recommend` for
    # P(clicked=True) against zero positive examples, which returns a degenerate,
    # near-constant ordering — and as the primary sort key below it would then
    # override text AND vector on every query after the very first. Gate on
    # `clicked=True` rows matching the context so the recommend has positives to
    # learn from (this is the docstring's "once clicks exist" contract).
    trained = 0
    if candidates and ctx:
        try:
            trained = client.query(
                {"from": "search_impressions", "where": {"$and": [ctx, {"clicked": True}]},
                 "limit": 0})["total"]
        except Exception:
            trained = 0   # impressions table not built yet — no clicks, no learned pass
    if trained > 0:
        request = {"from": "search_impressions", "where": ctx,
                   "recommend": "item_id", "goal": {"clicked": True}, "limit": 200}
        response = client.recommend(request)
        result.calls.append(("_recommend", request, response))
        for i, h in enumerate(response["hits"]):
            learned_pos[h.get("$value", h.get("item_id"))] = i

    # Balanced merge of the two candidate orderings — round-robin (interleave) so
    # an item ranked early in EITHER text or vector surfaces near the top: an
    # exact keyword hit is not demoted below a merely-similar one, and a
    # cross-lingual hit that text missed is not buried. Learned winners then ride
    # on top. Pure ordering, no score — the same "merge Aito's rankings" seam as
    # the learned pass (rule 2).
    big = len(candidates) + 1
    vec_order = [it for it, _ in sorted(vec_rank.items(), key=lambda kv: kv[1])]
    merged: list[str] = []
    seen: set[str] = set()
    for a, b in zip_longest([h["item_id"] for h in text_hits], vec_order):
        for it in (a, b):
            if it is not None and it not in seen:
                seen.add(it)
                merged.append(it)
    merge_rank = {it: i for i, it in enumerate(merged)}
    ordered = sorted(candidates, key=lambda h: (
        learned_pos.get(h["item_id"], big), merge_rank.get(h["item_id"], big)))
    hits = ordered[:top_n]
    result.derived = {"query": query, "kind": kind, "count": len(hits), "hits": hits,
                      "learned": bool(learned_pos), "semantic": bool(vec_rank)}
    return result


def serve(client: AitoClient, query: str, kind: str | None = None, top_n: int = 10,
          *, source: str = "dashboard", anchor_item_id: str | None = None,
          log: bool = True, embed=None) -> dict:
    """Serve a search the way the app does: ensure the index, rank (blended:
    text + semantic + learned), and (A+C) log the impressions server-side as a
    side effect. `embed` (embed.embedder(config)) turns on the semantic signal;
    None keeps pure text-match. Returns the ranked hits plus the `context_id` a
    later click attaches to. `log=False` serves without recording."""
    ensure_index(client)
    derived = ranked(client, query, kind=kind, top_n=top_n, embed=embed).derived
    if log:
        derived["context_id"] = _log_impressions(
            client, query, derived["hits"], source, anchor_item_id)
    return derived


def record_click(client: AitoClient, context_id: str, item_id: str) -> dict:
    """Record the item clicked for this context — the training signal. Append a
    `clicked=true` event rather than mutating the shown impression: v2 `_modify`
    is unreliable on this build (an update no-ops / drops the row — docs/24), but
    inserts are solid, and the learned ranking reads `clicked=true` rows as the
    positive examples. A dangling context/item raises (rule 3)."""
    _impressions_ready(client)
    rows = client.query({"from": "search_impressions",
                         "where": {"context_id": context_id, "item_id": item_id,
                                   "clicked": False}, "limit": 1})["hits"]
    assert rows, f"no impression for context {context_id!r} + item {item_id!r}"
    shown = rows[0]
    client.upload_batch("search_impressions", [{
        "impression_id": "imp_" + uuid.uuid4().hex[:12], "context_id": context_id,
        "query": shown["query"], "item_id": item_id, "position": shown["position"],
        "clicked": True, "at": _now(),
    }])
    return {"context_id": context_id, "item_id": item_id, "clicked": True}


def quick_find(client: AitoClient, query: str, limit: int = 6) -> dict:
    """A literal jump-to finder across the entities — companies, notes, todos,
    and contacts whose name/title (or a document's company/topics) contains the
    query. This is a LOOKUP for a "quickly open X" box, deliberately distinct
    from `search()` (the Aito-ranked smart search over content). Each hit carries
    a `target` hash-route so the top-bar finder can open it. Small tables, so a
    substring scan in Python is fine (a lookup, not ranking; rule 2)."""
    q = (query or "").strip().lower()
    if len(q) < 2:
        return {"query": query, "groups": []}

    def has(*vals) -> bool:
        return any(q in (v or "").lower() for v in vals)

    groups = []

    cos = [h for h in client.query({"from": "companies", "limit": 100000,
           "select": ["company_id", "name"]})["hits"] if has(h.get("name"))]
    if cos:
        groups.append({"kind": "company", "items": [
            {"label": c["name"], "sub": None, "target": f"company/{c['company_id']}"}
            for c in cos[:limit]]})

    docs = [h for h in client.query({"from": "documents", "limit": 100000,
            "select": ["doc_id", "title", "company", "topics", "noted_on"]})["hits"]
            if has(h.get("title"), h.get("company"), h.get("topics"))]
    if docs:
        groups.append({"kind": "note", "items": [
            {"label": d["title"], "sub": d.get("company") or d.get("noted_on"),
             "target": f"documents/{d['doc_id']}"} for d in docs[:limit]]})

    todos = [h for h in client.query({"from": "todos", "limit": 100000,
             "select": ["todo_id", "title", "area"]})["hits"] if has(h.get("title"))]
    if todos:
        # the dashboard's area-view keys differ from the raw area strings
        # (operations→ops, experiments→exp); anything without a matching view
        # falls back to "mywork" so a todo hit never misroutes.
        area_route = {"sales": "sales", "marketing": "marketing", "operations": "ops",
                      "rnd": "rnd", "experiments": "exp"}
        groups.append({"kind": "todo", "items": [
            {"label": t["title"], "sub": t.get("area"),
             "target": area_route.get(t.get("area"), "mywork")}
            for t in todos[:limit]]})

    cons = [h for h in client.query({"from": "contacts", "limit": 100000,
            "select": ["contact_id", "name", "company", "company_id"]})["hits"]
            if has(h.get("name"), h.get("company"))]
    if cons:
        groups.append({"kind": "contact", "items": [
            {"label": c["name"], "sub": c.get("company"),
             "target": f"company/{c['company_id']}" if c.get("company_id") else "sales"}
            for c in cons[:limit]]})

    return {"query": query, "groups": groups}
