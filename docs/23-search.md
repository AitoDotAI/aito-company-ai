# 23 · Smart search (unified index over content)

A search across the various content — documents, contacts, deals — ranked by
Aito text-match relevance. The same index the dashboard
**Search** view and the assistant's `smart_search` tool both use, so the agent
grounds its answers (RAG) on exactly what the operator can search.

## The index (`search_items`)

One denormalized table, an item per searchable thing, built by fanning out over
the sources (`search.build_index`): `item_id ("{kind}:{source_id}") · kind ·
source_id · title · text · tags`. It's app state / an index — excluded from the
CSV load/export machinery; `search.py` rebuilds it from the sources. Adding a
source is one adapter returning `{source_id, title, text, tags}`; today: `doc`,
`contact`, `deal`.

- **Kept fresh automatically.** The first search on a fresh instance builds the
  index whole (`ensure_index`); after that, every source write upserts just its
  own item (`search.index_row` / `deindex`, called from `log.py`) so the index
  never goes stale — a new contact/deal/document is searchable immediately,
  a deleted one drops out. The upsert is guarded (a no-op until the index is
  first built) so it can never leave a partial index. Documents are a source
  collection too now (docs/25), so a document write refreshes the view the same
  way — no on-disk files to reindex. A full **reindex** (`/api/search/reindex`,
  MCP `reindex_search`) still exists to rebuild the whole view on demand.

**Operational gotcha — the derived `$text` columns.** The view's `$text` merge
needs the sources' `search_title` / `search_text` (on `contacts` / `deals`) to be
**non-nullable Text**. On this Aito build that means they cannot be added to a
*populated* table in place: a non-nullable column needs a fill value, a nullable
one is refused by the view (`must be a Text column, but is NullableType`), and
Aito won't promote nullable→non-nullable. So when an instance predates these
columns, `create-schema` reports them under `needs_reload` and the only fix is to
**reload the table** (`export-all` then `load-rolodex` / `load-touches` /
`load-deals`), which recreates it with the columns populated — recomputed from the
exported rows, not an external CSV. (Reloading `contacts` also reloads `touches`,
which links into it.) Until that reload runs, the whole view fails to build and
search 500s — a symptom that predates any single deploy.

## The ranking is Aito's (rule 2)

`search.search(query, kind?, top_n)` ranks by Aito, never a Python heuristic:

- `$match` is **AND within one string** (a whole natural-language query matches
  almost nothing), so Python only *tokenizes* the query and ORs the terms — an
  item matches if it contains any term.
- `where` keeps the matching items; **`orderBy {"$p": <match>}`** ranks them by
  Aito's probability that they match. The model picks the query and narrates the
  hits; it never computes the ranking (rule 1/2).

Guards are loud (rule 3): an empty query or an unknown `kind` raises. The
booktest prints the Aito request/response and the ranked hits, and asserts the
numerical check (rule 4): a distinctive query ranks its item first.

## Semantic layer — embeddings (`search_vectors`)

Text-`$match` is exact and language-bound: a **French/Finnish query over English
content, or a paraphrase with no shared tokens, finds nothing.** So when an
embeddings deployment is configured (`Config.embed_enabled`, Azure OpenAI
`text-embedding-3-large` via `embed.py`), `search.ranked()` adds a semantic
signal:

- At **reindex** (`build_index(embed=…)`, run by `reindex_search` / the reindex
  endpoint — *not* on every write), each `search_items` row is embedded into
  `search_vectors` (`item_id, kind, title, vec`). Embedding is a load-time
  featurization; Aito owns the ranking (rule 2).
- At **query** time, `_vector_candidates` embeds the query and retrieves by
  `$nearest` over `search_vectors` (cosine) — candidates text-match never found.
- `ranked()` **interleaves** the text and vector orderings (round-robin, then the
  learned pass rides on top): an exact keyword hit is not demoted below a merely
  similar one, and a cross-lingual hit is not buried. Pure ordering, no Python
  score — the same "merge Aito's rankings" seam as the learned pass.

Everything degrades gracefully: no embeddings ⇒ pure text-match (unchanged); no
vector index yet ⇒ text-match until the next reindex. Two build-specific notes:
the embedding is requested at **1000 dimensions** (Matryoshka) because this Aito
build caps a `Vector` column at 1017; and `$vectorSimilarity` is not available on
this build, so retrieval uses `$nearest`. The flip is proven by
`book/test_search_vector.py` (gated on the embeddings deployment): a French query
goes from 0 text-match hits to the right documents.

## Surfaces

- **Dashboard**: Knowledge → **Search** — a query box + kind filter, results
  ranked most-relevant-first with a kind badge.
- **Assistant**: the `smart_search` read tool (docs/16) — find the right items,
  then read the source. Read-only, like the rest of the assistant's tools.
- **Agent (MCP)**: `search(query, kind?, top_n)` and `reindex_search()`.

## The impressions loop — the ranking learns from clicks

The ranking sharpens as results are used (operator decision **A+C**):

- **search_contexts** — one row per search served: the `query`, an optional
  `anchor_item_id` (the selected item), and the `source` (dashboard/assistant/mcp).
- **search_impressions** — one row per item shown for a context: `position`,
  `clicked`, `at`, linked to its context (so the ranking reads `context_id.query`).
  Both are app state; `item_id`/`anchor_item_id` are plain strings, not links,
  because `search_items` is rebuilt wholesale and Aito refuses to drop a table
  linked *into*.

**Serving logs impressions server-side** (`search.serve`) — telemetry on a read,
not an assistant write, so rule 1's fence holds even when the assistant searches.
**Clicks are the training signal**, recorded by the dashboard (tap a result) and
the **MCP `record_click`** tool (Claude-over-MCP may write; the in-app assistant
never does).

**The learned ranking** (`search.ranked`): text-match retrieves the candidates
(coverage, works cold), then Aito **`_recommend` with `goal: {clicked: true}`**,
conditioned on `context_id.query`, reorders them by the probability of a click
for a query like this. Both orderings are Aito's; Python only merges them
(learned winners first, the rest in text-match order) — it computes no score
(rule 2). Cold start (no impressions) is exactly text-match.

The round trip is covered (rule 4): a mid-ranked hit clicked across several
sessions rises to rank 1 on the next serve (`learned: true`), the click visibly
changing the ranking — `book/test_search_impressions.py`.
