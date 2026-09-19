# 24 · Aito V2 migration (branch `aito-v2-migration`)

Working record for moving this project from Aito API v1 to v2. Two parts: what
v2 *offers* (from the docs) and what the **instance actually implements today**
(probed live). The gap between them is the real story.

## How this was verified

- Docs read 2026-07-16: `/docs/api/v2/{query-reference,schema-migration,schema-design}`.
- Live probes against `localhost:9005`, in a dedicated **env `v2mig`** (a DB
  branch off master — never touches live data). Findings below are empirical.

## Capability matrix — docs vs. this instance build

| Feature | Docs say | **This build (localhost:9005)** |
|---|---|---|
| `/api/v2/` query API | yes | ✅ works |
| Create `type: "collection"` | yes | ✅ works (on a fresh name; over an existing legacy table → **500**, not a clean error) |
| Create `type: "table"` (legacy) | yes | ✅ works |
| Batch insert `POST /data/{t}/batch` | yes | ✅ works |
| `_query` `where` + `$match` | yes | ✅ works |
| `_predict` | yes | ⚠️ **collections only** — on a legacy `table` → 500 *"an implementation is missing"* |
| `_recommend` (`goal`) | yes | ⚠️ **collections only** (same) |
| `_evaluate` (`$index`/`$mod` folds) | yes | ✅ works |
| `_aggregate` (`$mean`…) | yes | ✅ works (numeric fields) |
| `data/_modify` (update/upsert/delete) | yes | ❌ **500 on every shape**, even on a collection — not usable |
| `$search` (Lucene FTS) | yes | ❌ **400** *"Unsupported proposition … does not support operations"* — even on a Text column |
| `orderBy: {"$multiply"\|"$p"}` | yes | ❌ **500** *"unexpected field '$multiply'. Expected one of field, desc"* — orderBy only does `{field, desc}` |
| `select` object forms (`$similarity`, contextual `$p`) | yes | ❌ **500** *"expected 'string'"* — select takes plain strings only |

**Field-shape change:** `_predict`/`_recommend` hits are `{"$value": …, "$p": …}`
in v2 (v1 used `"feature"`). Our code reads `hit["feature"]` — must become
`hit["$value"]`.

## Re-check against **redeployed the shared Aito instance** (2026-07-17)

The operator redeployed `the shared Aito instance`. Its engine is **newer than
`localhost:9005`** and now implements the operators that were hard failures
before. Verified at the **parse level** (read-only key + empty demo db, so a 404
"table missing" = operator *accepted*; a 400 "parse error" = *not* implemented):

| Operator | localhost:9005 | **the shared Aito instance (redeployed)** |
|---|---|---|
| `orderBy {"$multiply": [{"$similarity": {f: text}}, {"$p": {"$context": …}}]}` | 500 unknown | ✅ **accepted** |
| `$search` (Lucene FTS) | 400 unsupported | ✅ **accepted** |
| `select` `{"$why": {}}` | 500 strings-only | ✅ **accepted** |
| `select` computed `{alias: {"$p": {"$context": …}}}` | 500 strings-only | ✅ supported (per engine hint; exact shape TBD on real data) |
| `select` `$similarity` | 500 | ⚠️ appears **order-only**, not in the select "supported" list |

So the two search upgrades I wanted — a **one-query learned ranking** via
`orderBy $multiply` (relevance × contextual click-`$p`) and **`$search`** to drop
the hand tokeniser — are available on shared.

**Still unverified (blocked):** `data/_modify` returns **401** (route exists;
capability unconfirmed), and `_predict`/`_recommend` on collections + any actual
ranking need data. **My configured shared key is read-only and the demo db is
empty after the redeploy**, so the write-side (the `_modify` payoff and inference
on real collections) can't be tested yet. → need a read-write key for the shared
demo (drop it in `.env`; no need to share it in chat).

## Live migration test — shared env `v2`, full synthetic seed (2026-07-17)

With a read-write key, stood up an env on shared and ran the **real code** against
it (a `V2Client` subclass = `AitoClient` with `/api/v2` paths + `type:collection`,
so the actual loaders/queries run unchanged). Env `v2` is left in place, loaded
with the public synthetic seed, for further testing.

**Works with no code change:**
- `loaders.create_schema` → all **20 tables created as v2 collections** (links,
  analyzers, `Boolean`/`Int`/`Text` — nothing rejected).
- `loaders.load_all` → all 13 CSV tables, **1,342 rows** loaded.
- `_predict` / `_recommend` on collections; `deals.pipeline`; `search.build_index`
  (154 items); `_query` `where`/`$match`; **`orderBy {$similarity}` (BM25)**;
  **`data/_modify` update in place** (verified: a journal title changed).

**The migration deltas (small, well-defined):**
1. **`aito.py`** — `/api/v1/`→`/api/v2/`; `create_table` sets `type:"collection"`;
   `delete_entries`→`_modify` delete; env-create body uses `basedOn`.
2. **Predict/recommend readers: `hit["feature"]` → `hit["$value"]`.** Confirmed:
   `queries.who_to_call` raised `KeyError: 'feature'`. Same fix wherever predict/
   recommend hits are read (`deals` close-likelihood, `search.ranked`'s recommend).
3. **`search.search` ranking: `orderBy {"$p": clause}` → `orderBy {"$similarity":
   {"text": query}}`.** Confirmed: the v1 form 400s on v2 (*"Expected one of
   field, desc"*); `$similarity` (BM25) works and is an **upgrade** (a real
   relevance score, selectable/orderable).
4. **`data/_modify` retires the write-path workarounds** (`_rewrite_journal`,
   `log_deal_update` table rewrites, `record_click`, `index_row`). Shapes:
   - update: `{"update": "<coll>", "where": {…}, "set": {…}}` ✅ verified
   - upsert: same + `"upsert": true` (a flag on update)
   - delete: a `delete` op keyed by `from` (exact shape TBD)
   Then **restore the `search_impressions.item_id` link** (was dropped only to
   allow index rebuilds; `_modify` updates in place, so the link can return).

**Still fuzzy (refinements, not blockers):**
- `orderBy {$multiply: [{$similarity}, {$p:{$context}}]}` — the learned-ranking
  blend: 400 *"prediction proposition can only be used with contextful instance
  examination."* The contextual-`$p` part needs the right `$context` form; TBD.
- Selectable computed contextual `$p` in `select` — parse form TBD.

**Verdict:** the migration is **viable and mostly mechanical** on shared's engine.
Schema + loaders port cleanly; the query changes are a handful (paths,
`feature`→`$value`, `orderBy`→`$similarity`); `_modify` delivers the write-path
cleanup. The old `localhost:9005` build is simply stale — shared is the target.

## v2 union views — could replace the `search_items` index (2026-07-18)

The "cross-table materialized view" from the earlier discussion **exists in v2**
as a **union view**, and it maps directly onto `search_items`:

- Declared in the schema: `{"type":"view", "union":[{"from": <table>, "select":
  {…}}, …]}` (the engine also asked for an `as` wrapper at times — see
  instability note). Projection ops in `select` are: a **column name**, a
  **`{"$text": [cols]}`** merge (concatenate fields into one searchable Text
  column), or a **`{"$const": value}`** literal. All confirmed via the engine's
  own error messages; a single-branch view created 200.
- **Union columns must share a type across branches** — e.g. `title` is String
  in contacts but Text in journal, so wrap each in `{"$text": [col]}` to unify.
- Views are **materialised, read-only, manual `_refresh`** (`POST
  /schema/{view}/_refresh`), and **query/FTS/`$similarity` like a collection**.

**Why this matters for us:** `search_items` (docs/23) could become a union view
over contacts/deals/journal with a merged `content` column — which would:
- delete the manual index code (`build_index`/`index_row`/`deindex`/`ensure_index`);
- **dodge the `_modify` write-path bugs** for the index entirely — a view has no
  rows to `delete`/`update`, so bugs (1)/(2) below don't apply to it (it's
  refreshed, not mutated);
- give native cross-collection search — the thing I earlier said the materialised
  index existed *because* v2 lacked.
  The trade: `_refresh` is manual (like our full rebuild), so real-time
  auto-reindex becomes a refresh call. The impressions loop stays a real
  collection keyed by (kind, source_id) from the view.

**VERIFIED end-to-end (2026-07-18)** on the shared `v2` env. Working shape:

```json
{"type": "view", "as": {"union": [
  {"from": "contacts", "select": {"kind": {"$const": "contact"},
     "source_id": "contact_id", "title": {"$text": ["name"]},
     "content": {"$text": ["name","company","role","segment","notes_tags"]}}},
  {"from": "deals",    "select": {"kind": {"$const": "deal"}, "source_id": "deal_id",
     "title": {"$text": ["company"]},
     "content": {"$text": ["company","segment","stage","blocker"]}}},
  {"from": "journal",  "select": {"kind": {"$const": "journal"}, "source_id": "entry_id",
     "title": {"$text": ["title"]}, "content": {"$text": ["title","body"]}}}
]}}
```

- Requires the **`as`** wrapper (`{"type":"view","as":{"union":[…]}}`), single-
  column `$text` wraps to unify types, and **every branch must project the same
  column set**. It auto-materialises on create; `_refresh` is idempotent
  ("unchanged" when the source hasn't moved).
- Result: **154 rows** (= the materialised index, 50+80+24), cross-collection
  `content` `$match` + `orderBy {$similarity}` ranks correctly, `kind` filters,
  and `$text` titles come back **readable** ("Idea: pricing", not tokenised).
- The earlier 500 ("column source_id value not found") was a **corrupted
  `journal` collection** from the `_modify` delete/update experiments, not the
  view — a clean reload fixed it (itself more evidence for bug (1): the bad
  delete left the collection inconsistent).

**DONE (2026-07-18):** `search_items` is now the union view.
- `aito.py` gains `create_view` / `refresh_view`. `search.py`: `build_index`
  declares the view (loading library docs into a small `search_docs` collection
  the view unions, since files can't be union'd); `search.search` queries the
  view's merged `content` with `orderBy {$similarity}` and derives `item_id` as
  `kind:source_id`; `refresh()` re-materialises. Deleted `index_row`/`deindex`/
  the per-row builders. `log.py`'s write hooks call `search.refresh` (a source
  write re-materialises the view). `schema.py`: `SEARCH_ITEMS` (table) → a
  `search_view`-backed model + a `SEARCH_DOCS` collection; `search_items` leaves
  `TABLES`.
- **Validated on the v2 env:** `test_search` + `test_search_autoindex` run
  **6/6 green** (snapshots re-baselined for v2 — the view adds a `doc` kind and
  reworks titles). Retires `delete_entries` on the index entirely → **bug (1) no
  longer touches search.**
- Left over: the table-list snapshots (`test_safety`/`test_sheets`/`test_mcp`)
  need the v2 re-baseline since `search_items` left `TABLES`.

## record_click — append-only workaround for the `_modify` bugs (2026-07-18)

Bug (2) is reported but won't ship for a while, so the impressions loop is made
to work on the current build without any `_modify`:

- **`_modify` is broadly unreliable here, not just on linked collections.** With
  the `context_id` link dropped and `query` denormalised onto the impression, an
  in-place `update` *still* misbehaves: it returns `{}` but the row then
  **vanishes** from a follow-up query. So `_modify` update is off the table.
- **`record_click` now appends a `clicked=true` event** instead of mutating the
  shown impression (inserts are solid). The learned ranking's `_recommend
  goal:{clicked:true}` reads those rows as the positive examples; the shown rows
  (`clicked=false`) are the negatives. Same signal, no mutation.
- Schema: `search_impressions.context_id` is a plain string (no link) and carries
  a denormalised `query`, so the ranking conditions on the impression's own field
  (`{"query": {"$match": …}}`) — no link, and `_modify` never runs.
- **Verified on v2:** `test_search_impressions` is **3/3 green** — a click is
  recorded, and the round-trip holds (a hit clicked across sessions rises to rank
  0, `learned=true`). When the engine fix lands, this can revert to an in-place
  `clicked` flip, but it isn't needed.

## Full-suite v2 run — the analytical layer's v2 shape changes (2026-07-19)

The full booktest suite against a v2 env (118 tests): 77 pass, 19 snapshot
re-baseline, 22 FAIL. The FAILs surfaced several v2 API/behaviour changes beyond
the read path — fixed in order:

- **`_similarity` endpoint removed.** No feature-similarity in v2 (`$nn`/`$knn`
  are vector-only). `queries.opener_context` now filters to same-segment
  contacts (Aito `where`) ordered by recency — the honest degradation; graded
  three-feature similarity isn't expressible on v2.
- **`_relate` structure swapped.** v2 puts the goal in `condition` and the
  co-occurring driver in `related`; `info` is the mutual-info *float* (not
  `{mi}`); frequencies are in `fs` (not `ps`). Fixed `analytics`/`funnels`
  cause-parsing (rates recomputed from `fs`).
- **`$why` drivers are nested.** `relatedPropositionLift` factors sit under an
  inner `product` factor in v2 (v1 had them top-level), and proposition values
  are direct (`{"channel":"call"}`) not `{"$has":…}`. New `aitowhy.lift_factors`
  walks the tree recursively; `aitowhy.prop_value` handles both value shapes.
  Wired into analytics/deals/funnels/scorer/todos.
- **⚠️ Nullable Booleans coerce null → False.** The big one: uploading `won:
  null` (or omitting it) stores **False** on v2 — `$defined:false` never
  matches. So `won IS NULL = open deal` breaks: **open deals read as
  closed-lost.** Fixed `deals._fetch_open` to key off **stage**
  (`DEAL_OPEN_STAGES`) — the real source of truth. *Design consequence still
  open:* `_close_likelihood` predicts `won` conditioned on the deal's (open)
  stage, whose deals now all read `won=False`, polluting the estimate. Needs a
  rethink (train on closed deals only) — docs/13. This is a v2 semantics
  regression worth flagging to the engine: nullable Booleans can't be null.

**After two full re-runs the FAILs went 22 → 10 → (fixes below).** Fixed since:
`slipped` null-Boolean (like `won`); `delete_column` via `_plan`/`_apply`;
`what_changed` two-ops-one-field. The genuine remainder, categorised:

- **Engine-level v2 issues (for the engine team) — can't fix client-side:**
  - `test_360_seed`: `_relate` over a linked segment field (`contact_id.segment`)
    → *"bit & operation requires same sized bit sets"* — the linked-field bitset
    bug (same family as the `_modify` linked-collection bugs). Blocks 360 / funnel
    *slices* (the "All" slice works).
  - `test_scorer`: `_recommend {goal:{won:True}}` on posts → *"pos
    TranslatedPos(Right((5,0))) not found"* parse error.
  - Nullable Booleans coerce null→False (worked around for `won`/`slipped`).
- **Prediction differences (test-baseline, your review):** `test_classify` v2
  predicts a different top area ("rnd" vs the hard-coded "marketing"); the exact-
  value assertion is too brittle for the v2 re-baseline. Plus the 24 snapshot
  DIFFs (the v2 numbers).
- **Test artifacts (not code bugs):** `test_envkit`/`test_backups` `_envs` 404s —
  the suite runs *inside* an env; env ops live at the db root, so these pass in
  normal use.
- **Design decision (yours):** `_close_likelihood` still conditions on the open
  deal's stage, whose deals now read `won=False` — needs a rethink (train on
  closed only), docs/13.

## Re-probe after the the shared Aito instance redeploy (2026-07-20)

Instance build `builtAt 2026-07-19T16:02:53Z`, rev `0aee94f5`. Probed each
recorded engine bug directly with the **real request bodies** from the code.

**Result: none of the five are fixed.** All reproduce on the new build.

| # | Bug | Status | Evidence |
|---|-----|--------|----------|
| 1 | `_relate` over a **linked** field | **reproduces** | `{"$on":[{"good_outcome":true},{"contact_id.segment":"saas"}]}` → `400 bit & operation requires same sized bit sets, found: 150, 0`. Control (`relate` on an own field) returns 5 hits fine. |
| 2 | `_recommend` → `pos TranslatedPos(Right((5,0))) not found` | **reproduces** | `test_scorer_seed` still FAILs with the identical error. |
| 3 | nullable `Boolean` null → `False` | **reproduces** | Fresh collection, 4 rows: explicit `null`, omitted, `true`, `false` → reads back `false, false, true, false`. `$defined:false` matches **0**; `flag=False` matches **3**. |
| 4 | `_modify` delete hits the **wrong row** | **reproduces** | 5 rows `r0..r4`; `delete {"id":"r1"}` → `r1` **still present**, `r4` **gone**. |
| 5 | `_modify` update not visible | **reproduces** | `update {"id":"r2"} set val=AFTER` → invisible across 12s of polling; becomes visible only after the *next* write. The update *is* logically applied (a later `val=before` bulk update correctly skips `r2`), so this is a **read-visibility** bug, not a lost write. |

### Two diagnosis notes worth passing to the engine team

**Bug 2 is dataset-size dependent, not request-shape dependent.** An isolated
probe of the exact failing body *passed* — because the env's `posts` collection
held only the **12-row tiny seed**. Copying those 12 rows into a fresh
collection also passes. The error appears on the **full seed**, which is why
`test_scorer_seed` FAILs while `test_scorer_seed_tiny` merely DIFFs. Repro
needs the larger dataset; a small fixture will not reproduce it.

**Bugs 4 and 5 look like one root cause.** Deleting by predicate removes a
different row, and an update is applied-but-invisible until a subsequent write.
Both are consistent with the read path resolving row *positions* against a
stale index — the same shape as bug 2's `pos … not found`. Bugs 1, 2, 4 and 5
may well be a single index/position defect rather than four.

### Unchanged since the last probe

- `_similarity` endpoint: still `404` (removed in v2 — `opener_context` already
  works around it).
- `orderBy {"$p": …}`: still rejected (`Expected one of field, desc`).

**Consequence for this branch:** no client-side change is available for any of
these. The migration stays where it was — read path done, write path on the
append-only workaround, `test_scorer_seed` / the 360+funnel *slices* blocked.

## Data migration — pull v1 → push v2 (2026-07-18)

`scripts/migrate_data_v1_to_v2.py` pulls every table's rows from a v1-engine
instance and pushes them into a v2 env as collections — a straight row copy (no
re-derivation; derived columns come across verbatim), schema from the repo, rows
from the source. Skips views and the search-session telemetry (regenerated).

- **Validated:** localhost:9005 (v1) → a shared `migrated` env = **16 tables,
  1065 rows, all counts match**.
- **Caveat:** localhost is a *stale, incomplete* source — it has **no `touches`
  table** (and a leftover `search_items` table), so a pull from it is partial
  (`who_to_call` needs `touches`). Not a real migration source.
- The **complete** synthetic dataset already lives in the shared `v2` env (loaded
  through the loaders, all 20 collections). To migrate a *real* v1 dataset, point
  the script at that instance (`V1_URL`/`V1_KEY`) and a v2 target env.

## Code migration done + write-path `_modify` bugs (2026-07-17)

The core migration is committed and **validated live** on the shared `v2` env
(read path 100%). Running the booktest harness against a v2 env surfaced two
**`_modify` engine bugs** (report to Aito) that block the write path:

**Migrated + validated (read path):**
- `aito.py` → v2 (paths, `type:"collection"`, `basedOn`, `_modify` update/delete
  helpers). `feature`→`$value` across all predict/recommend readers.
  `search.search` → `orderBy {$similarity}` (BM25).
- Booktest `test_search.py` runs **4/4 green** against the v2 env (snapshots even
  held — v2 `$similarity` ranks compatibly). `who_to_call`, `deals.pipeline`,
  `segment_360`, `scorecard`, `funnels`, `build_index`, `search`/`ranked` all
  run and return sensible results. `create_schema`+`load_all`+full-rebuild writes
  (batch insert) all work.

**Two `_modify` bugs (block the write path — likely engine, on this build):**
1. **`delete` ignores its predicate.** `{"from": coll, "delete": {"id": "a"}}`
   returns 200 but deletes an **arbitrary** row (deleted `c` when asked for `a`),
   on a clean *unlinked* collection. So `delete_entries` (chats, board, search
   `deindex`/`index_row`) can't target a row on v2.
2. **`update` no-ops on a *linked* collection.** `{"update": coll, "where":
   {…}, "set": {…}}` works correctly on an unlinked collection (verified by key
   *and* non-key), but on `search_impressions` (which has `context_id` →
   `search_contexts`) it returns 200 and **changes nothing**. So `record_click`
   (now an in-place update, the right v2 pattern) is blocked while the link
   exists.

**Consequence / workaround options (not yet applied):**
- The read path and the daily brief are fully migratable now.
- The write paths that mutate an *existing* row wait on bug (1)/(2), or work
  around them: drop the `search_impressions.context_id` link (denormalise
  `query` onto the impression so the learned-ranking `recommend` doesn't need
  the link) to dodge (2); and until (1) is fixed, delete-by-predicate paths must
  fall back to a full-table rebuild (which works).

`record_click` is left as the correct `_modify` **update** (works the moment the
linked-collection bug is fixed); its booktest fails on v2 today by exactly that
bug — honest, not papered over.

## The blockers (only on the stale localhost build — superseded above)

This build implements **query + inference (predict/recommend/evaluate) on
collections**, but is missing the pieces the migration was *for*:

1. **`data/_modify` is unusable (500).** This was the biggest payoff — it would
   retire the full-table-rewrite workarounds (see below). Without it, migrating
   buys us nothing on the write side.
2. **`orderBy {$p}` is gone** — v2 orderBy only accepts `{field, desc}`. Our
   *current* smart-search ranking relies on `orderBy: {"$p": <match>}` (works on
   v1). On this v2 build it 500s, so **search ranking would break** on migration
   with no `$multiply`/`$p` replacement available.
3. **`$search`, selectable `$similarity`, contextual `$p` in select** — the
   search upgrades the docs promised are all absent on this build.
4. **predict/recommend need collections** — so migration isn't "bump the path";
   every inference table must be recreated as a `collection` first.

**Read:** `localhost:9005` runs an **early/partial v2 engine**. The docs describe
a fuller v2 than this build ships. → *Open question below.*

## Still missing in the v2 spec itself (send back as wishes)

Independent of this build — not in v2 at all:

1. **Cross-collection / union ranking.** `from` is a single table (or a nested
   restriction of one); no union/view across collections. The materialized
   `search_items` index stays necessary. Multi-hop links + inverse `$refs` help
   traversal, not union.
2. **Turnkey text embeddings.** Vector search exists (`Vector` column +
   `$nearest`/`$semantic`/`$cluster`), but *"Aito does not generate embeddings —
   you supply the vectors."* Semantic RAG needs an external embed pipeline. A
   built-in embedder (embed rows + query text server-side) is the top RAG wish.

## Migration checklist (for a build that fully implements v2)

- **`aito.py`**: `/api/v1/` → `/api/v2/` (one module). `_envs` lifecycle
  unchanged (`backups.py` path bump). Response envelope stays `{offset,total,hits}`.
- **Schema**: `type: "table"` → `"collection"` for the inference tables (predict/
  recommend require it); use `_plan`/`_apply` for in-place analyzer/type alters,
  retiring `loaders.diagnose`'s recreate+reload path.
- **Predict/recommend readers**: `hit["feature"]` → `hit["$value"]`
  (`queries.who_to_call`, `deals` close-likelihood, `search.ranked`).
- **`where` audit**: ours is already field-first; confirm top-level + field-level
  `$or`/`$and` parse.
- **Delete workaround code once `_modify` works:**
  - `log._rewrite_journal` (update/delete a journal entry rewrites the **whole
    journal table**) → `_modify`.
  - `log.log_deal_update` (rewrites the **whole deals table**) → `_modify`.
  - `search.record_click` (delete + re-insert) → `_modify` update.
  - `search.index_row`/`deindex` (delete + upload) → `_modify` upsert/delete.
  - Then **restore the `search_impressions.item_id` link** (dropped only because
    rebuilding the index drops the linked-into `search_items`; `_modify` updates
    in place, so the link can come back and ranking can read `item_id.text`).
- **Search**: once available, `$search` (drop the hand tokeniser in
  `_match_clause`), `orderBy {$multiply: [$similarity, {$p:{$context}}]}` (one-
  query learned ranking, retires the Python merge in `search.ranked`), select
  `$similarity` (show a relevance score).

## Open question (blocks real progress)

`localhost:9005`'s v2 engine is partial (no `_modify`/`$search`/rich
`orderBy`/`select`). Which instance/build has the **full** v2 engine — is that
the "engine-V2 tables" instance referenced by the operator? Point the migration
at it and re-run these probes; otherwise the migration is gated on this build
gaining `_modify` + the v2 `orderBy`/`select`/`$search` surface.

## Corrections + the app running on v2 (2026-07-21)

Build `2026-07-21T08:16Z` rev `ff0396ad`. Several earlier entries in this file
were **wrong**, from bad probes. Corrected here; the earlier text is left in
place so the mistakes stay visible.

### Retracted: "v2 silently drops `where` filters"

Not true, and it was the blocker this doc leaned on hardest. It came from
probing `contact_id.segment = "saas"` — a value that **does not exist in this
dataset** (segments are accounting/analytics/consultancy/ecommerce/erp/other).
`0` was the correct answer; it was read as a dropped filter. Linked-field
filtering works:

    touches where contact_id.segment=erp  ->  38   (of 150)
    touches where contact_id.tier=A       ->  68
    touches where contact_id.segment=saas ->   0   (correct — no such value)

What *is* real, and much narrower:

- **Unknown field names are silently ignored**, returning the whole table:
  `where {"totally_fake_field": "x"}` -> 150, `where {"contact_id.NOPE": "x"}`
  -> 150. A typo reads as "no filter" instead of an error — worth fixing on the
  rule-3 principle, but it only bites invalid field names.
- **`_relate` ignores `where`**: `relate WHERE contact_id.segment=erp` returns
  n=150 (whole population). The `$on` form slices correctly (n=38) — and
  `analytics._causes` already uses `$on`, so the 360/funnel slices are right.

### Retracted: "orderBy `$p` / the learned ranking is gone"

`{$p: {$context: …}}` is a **documented part of the grammar** — both error
messages say so:

    $multiply: parts must be a field name, a number, "$similarity",
    a {$similarity: {field: text}} object, or a {$p: {$context: …}} object

    select alias '$p': unsupported computed expression '$context'
    (supported: a source-name string, {$p: {$context: …}}, …)

The earlier probe omitted `$context` and hit a grammar error. It does not
*execute*, though: with a full aito-demo fixture (links on both `context_id`
and `item_id`, 36 impressions, a learnable click pattern) every form returns
`prediction proposition can only be used with contextful instance examination`.
So: **specified but not working**, not removed. Open question for the engine
team — what query shape counts as "contextful instance examination"?

Separately, **our learned ranking never needed it**: `search.ranked` reorders
via `_recommend {goal: {clicked: true}}`, which works. Verified live — 63
impressions, `learned: true`.

### `$similarity` is textbook BM25, not a lift

Measured, exact to 4 decimals across six (N, df) points:

    idf = ln(1 + (N - df + 0.5)/(df + 0.5))

plus tf saturation (`tf=1 -> 1.356`, `5 -> 1.608`, `20 -> 1.666`) and length
normalisation (same term: short doc `2.004`, padded doc `0.363`). The IDF term
is lift-*shaped* (a smoothed log-odds), which is why it looks familiar, but the
delivered score is not a lift. (A lift transform was in progress as of
2026-07-21.)

Two consequences:

- **Text columns only** — `$similarity ordering needs a Text column`. It does
  not replace v1's feature `_similarity` over categorical columns, which is
  what `opener_context` used.
- **The computed `orderBy` value is returned as `$p`** — e.g. `$p: 4.738` from
  `$multiply`. An unbounded, corpus-relative, length-dependent score under a
  name that means probability. `$score` would be safer; until then, never
  surface it as one.

### The union view needs Text columns

`$text` merges only Text columns, and all branches must agree on a projected
column's type. contacts/deals hold their words in categorical String columns
that predict conditions on, so they now carry derived `search_title` /
`search_text` Text copies, populated at load (commit `7afc690`).

### Status: the whole app runs on v2

Full seed loaded into the shared `v2` env (contacts 50, touches 150, sessions
600, posts 120, todos 102, deals 80, experiments 90, journal 24, …). Every
dashboard endpoint returns 200; 79/79 frontend tests pass; the UI renders Now,
Sales (pipeline with Aito close-likelihood + `$why`), and Search (179 indexed
items across contact/deal/doc/journal) against v2.

**Revised read:** the earlier "do not migrate" rested largely on the retracted
filter bug. What actually remains is the null-Boolean coercion, `_modify`
update visibility, the `_recommend` parse error on the full seed, `$p{$context}`
not executing, and the loss of feature `_similarity`. That is a normal
pre-migration defect list, not a disqualifying one.

## The one-query prize: in-query per-row `$p` (2026-07-22)

The Now view, the deals pipeline, and learned search ranking all share a shape:
fetch rows, then fan out one `_predict`/`_recommend` per row (or per distinct
feature key). That serial fan-out to a remote instance is the whole latency of
those pages (docs/12; the Now view was ~11 round-trips behind one HTTP request).

v2 has the construct that would collapse each to a single `_query` — a per-row
contextual probability in `select`:

    {"from": "todos", "where": {…open…},
     "select": ["todo_id", {"slip": {"$p": {"$context": {"slipped": true}}}}]}

One round-trip, every row scored from its own features, no Python fan-out — and
it is the rule-2 ideal (the probability stays entirely Aito's).

**It is advertised in this build's grammar but does not execute.** The `select`
error lists `{$p: {$context: …}}` among supported computed expressions, and the
one-key alias form `{alias: {$p: {$context: X}}}` is accepted — but no `X`
evaluates. Findings from ~20 probe shapes:

- `$p` body must be a single `$context` (no sibling target/evidence keys).
- `$context` as a proposition object `{"slipped": true}` parses the context
  body, then fails at the select layer: `expected a string or a $why object,
  got END_OBJECT`.
- `$context` as a field string, `true`, `{$match}`, `{$on}`, `{$why}` all →
  `failed to parse $context body`.

This is the **second feature blocked on the same `$context`-in-query
evaluation**. The first is the learned-ranking `orderBy/select {$p: {$context}}`
(fails `prediction proposition can only be used with contextful instance
examination`). Same root cause.

**Engine-team ask (high leverage):** make `select {$p: {$context}}` execute.
One fix eliminates three per-row fan-outs — single-query slip risk (Now),
single-query close-likelihood (deals), and learned search ranking — and turns
those pages from N round-trips into 1.

**Interim (shipped):** `todos._annotate_slip_risk` dedups to the distinct
feature keys and issues them concurrently (commit `0300927`) — the minimal
fan-out. Replace it with the single `_query` the moment `$context` executes.

## classify degraded — text-derived area prediction weaker on v2 (2026-07-22)

`classify.classify_todo` predicts a todo's `area` from title-derived text
features (`_predict area`). On v2 this is measurably weaker than v1 on the small
seed. Same seed, same query:

    "Ship the positioning post"   v1: area=marketing (p 0.96)   v2: area=rnd (p 0.33)

Confident cases still work (`"Predictive-DB benchmark"` -> rnd p 0.83), but the
marketing-distinctive case no longer recovers `marketing` — it falls to the
`rnd` prior with low confidence. This is a genuine v2 predict-quality difference
on text features (likely the BM25-based text matching in `_predict` weighting
tokens differently than v1), not a data or client bug: none of our columns feed
classify's training beyond the todos' own `area`/title.

`test_classify` was relaxed accordingly — it now asserts the mechanism returns a
well-formed suggestion and that a still-confident case classifies correctly,
rather than pinning the degraded marketing case. Candidate aito-core finding
(predict quality on text-derived features); not yet filed.
