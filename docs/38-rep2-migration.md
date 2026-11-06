# 38 — Moving the tables from rep1 to rep2 (design note, for review)

Status: **plan only, for Antti's approval.** Nothing here changes a schema
until he approves it. Board item td-20261106100502161570.

## Where we are

26 of our 27 tables are rep1 (`"type": "table"`, Aito's TableDb). Only
`web_steps` is rep2 (`"type": "collection"`, CollectionDb), because a
self-link needs it (docs/37). The client already speaks **`/api/v2` for every
call** (`aito.py`): there is no v1 endpoint to retire on our side. The move is
from one storage engine to the other under the same API.

Aito's direction is clear: v2 is built for collections, and a rep1 table's
v2 support is "deliberately minimal" because v1 is being retired
(aito-core `collectiondb-v2.md`, `query-types-v2.md`).

Aito has an in-place move: the `_modify` verb `migrate`
(`{"migrate": "<table>", "engine": "v2"}`, or `POST /schema/{table}/_migrate`).
It rebuilds the table as rep2 under the same name, keeping schema and rows.
Several `migrate` ops in one request commit atomically, and warm the table
before it becomes visible. **There is no reverse migration.**

## What the probe showed (6.11.2026)

A throwaway local container, `ghcr.io/aitohq/aito:v2.12.0` (ef016d9b), held
two linked tables (a link, Text, String and Boolean columns), once as rep1 and
once as rep2. The same calls ran against both
(`.ai/maintenance/probe_rep2_ops.py`):

| call | rep1 | rep2 | answer shape |
| --- | --- | --- | --- |
| `_predict`, with `$why` | ok | ok | same keys; `$why` is `{type: product, factors}` on both |
| `_predict` of a link | ok | ok | same |
| `_recommend` with a goal | ok | ok | same |
| `_match`, `_similarity` | ok | ok | same |
| `_relate`, a field array and through a link (`co.name`) | ok | ok | same hit keys (`condition fs info lift n ps related relation`) |
| `_query` with `$match`, `$has`, a link path | ok | ok | same |
| batch upsert, `?on_conflict=update` | needs a declared top-level `primaryKey` on **both** | | |
| `migrate` of the linked pair in one `_modify` | ok: `type: collection`, `engine: v2`, link kept, 60 of 60 rows, `_relate` through the link still answers | | |

On that data the numbers were **identical** too: predict `$p` 0.9535,
relate lift 2.838, recommend `$p` 0.3017 on both engines. A toy table proves
the shapes, not the numbers on our data: see "How we judge it" below.

Two findings differ from the docs. Both were seen on 2.12.0 and should be
re-checked on internal's build:
- `$match` answered on rep1 here, though the docs call it collection-only.
- Upsert by `primaryKey` worked on rep1 when the key was declared through the
  v2 schema route. So **upsert is not a reason to migrate by itself**: the
  duplicate-on-resend hazard (td-20261106110308568348) is closed by declaring
  `primaryKey`, which is its own schema change on either engine.

## What rep2 gives us

1. **Links between our tables and `web_steps`.** A link can't cross engines,
   so today `web_steps` can't link to `web_sessions`, `web_visitors` or
   `posts`. That's docs/37's post → visit → steps → KPI chain in one graph,
   instead of the step ids we parse.
2. **`$patterns` on every table.** It's refused (`501`) on rep1, and used
   today only on `web_steps`.
3. **Cheaper writes to link targets.** On rep1, every write to a table others
   link to costs time in proportion to the linking rows, and blocks other
   databases' writes. A 100-row `_modify` is ~50 ms on a collection, up to
   ~30 s on a large rep1 link target (aito-core changelog). `companies`,
   `contacts`, `deals` and `posts` are our link targets.
4. **In-place column alter**, plus `_plan`/`_apply`, on collections. That
   removes our `needs_reload` path in `create_schema`, and some of the
   drop-and-reload fallback in `delete_column`.
5. Aito's own path forward: new engine features land on collections.

## What can break, or changes

- **`_evaluate`** on a collection covers only `predict` and `estimate`.
  `recommend`, `relate`, `match` and `similarity` are refused on collections
  ("not yet"). We don't call `_evaluate` in `src/` today, but any notebook or
  maintenance script that evaluates a `_recommend` (for example
  search_impressions) loses it.
- **Cross-engine links during the move.** While one table of a linked pair is
  rep2 and the other rep1, a query that follows the link is a `400`. Each
  linked group must move **in one `_modify`**.
- **The `search_items` view** unions `contacts`, `deals` and `documents`.
  Whether a view may union tables of different engines is untested, so these
  three move together with their group, and the view is refreshed and checked
  right after.
- **Vectors** (`search_vectors.vec`, `$nearest`): verify on a branch that the
  column and its queries behave the same after the move.
- **`schema.py`** must flip each moved table's `"type"` to `"collection"` in
  the same release, or a fresh clone and the booktest env would create rep1
  again. `create_schema` only adds missing tables and columns and never
  compares types, so a deploy's `create-schema` can't undo a move.
- A stale comment: `search.py` says documents are "a real collection now
  (docs/25)", but `schema.DOCUMENTS` is `"type": "table"`. To be fixed with
  the move.

## Which queries may change answers

By shape: **none** on 2.12.0, per the probe. By numbers, every inference on
a moved table could change, because the engines score separately. That
change counts as prediction semantics, so Antti sees it per group, as
booktest diffs. The surfaces by group:

| group | tables | inference that reads them |
| --- | --- | --- |
| standalone, app state | `tokens`, `users`, `assignments`, `chat_messages`, `routines`, `changelog`, `web_suppressed`, `search_contexts` | none or lookups only: no prediction |
| standalone, inference | `todos`, `decisions`, `events`, `materials`, `channels`, `sessions`, `search_impressions`, `search_vectors` | todo classify (`_predict`), decision scorecard, website funnel (`sessions`), smart-search ranking (`_recommend` over impressions), semantic search (`$nearest`) |
| web | `posts`, `experiments`*, `web_sessions`, `web_visitors` | `web_kpis` / `web_view` (`_relate`, `_predict` next path), experiment board (`_predict`), post scorer (`_predict`/`_recommend` on posts), attribution |
| sales graph | `companies`, `contacts`, `deals`, `deal_events`, `documents`, `touches` (+ the `search_items` view) | the morning brief, who to call, segment 360 and funnels (`_predict`/`_recommend`/`_relate` on touches), deal close-likelihood, knowledge graph (`$refs`, link paths), `_match` in validate/chats |

\* `web_sessions.experiment_id` links to `experiments`, so `experiments`
moves with the web group.

## The order: smallest and least linked first

1. **App-state tables** (no links, no inference): proves the mechanics, the
   backup and the verification, at no risk to any answer.
2. **Standalone inference tables**, one at a time: the first number changes,
   each reviewable alone.
3. **The web group** in one `_modify`: `posts`, `experiments`,
   `web_sessions`, `web_visitors`. After it, `web_steps` can link to
   `web_sessions` (a follow-up schema change, separately approved).
4. **The sales graph** in one `_modify`, last: the core of the brief.

Each step is a separate release and a separate approval.

## How we judge it (rule 4)

For each step, before touching internal:
1. **Booktests on rep2.** Flip that step's tables to `"collection"` in
   `schema.py` on a branch, and run the whole suite. The snapshot diffs are
   the before/after on the seed data. Antti and the CPO review them; an
   unexplained number change stops the step.
2. **A rehearsal on a branch of internal.** Branch internal into an env
   (copy-on-write, docs/21), run the `migrate` batch there, and run a
   read-only verifier against master and the branch:
   - per table, the row count and the schema columns;
   - every link resolves;
   - a fixed set of reads gives the same answer shape, with their numbers
     side by side: brief, who_to_call, deal_pipeline, segment_360,
     web_kpis, web_paths_to, smart_search.
   The internal build's `migrate` support is confirmed here first.

## The cutover

Outside the 08:00–10:00 no-touch window, with no deploy or bulk write
running.

1. A fresh backup env (`backups.py`, the guarded snapshot), its name noted.
2. One `_modify` with the step's `migrate` ops (with warm queries for the
   text-heavy tables).
3. The same verifier as the rehearsal, against the backup: counts equal,
   links resolve, the fixed reads answer. For web tables, also
   `verify_salted_repull.py` / `verify_steps.py`, as on every re-pull.
4. Refresh `search_items` and check it, when the step touches its sources.
5. Deploy the release that flips `schema.py` for those tables.

## Rollback

There is no reverse `migrate`. Rollback is **promoting the backup env from
step 1** (docs/21's guarded restore), which brings back the rep1 tables as
they were at the snapshot. Writes made after the snapshot are lost. So the
cutover runs in a quiet hour, the pull and routine timers are paused for it,
and the decision to roll back is made at verification (step 3), before
anyone writes again. The code side rolls back by reverting the `schema.py`
flip.

## Asks

- **Antti:** approve the plan and its order, and each step's booktest diffs
  as it comes. Each cutover on internal is a separate yes.
- **aito-core:** confirm `migrate` on internal's build (2.12.0-dev+11141e6c),
  and whether a view may union mixed engines. The probe's two doc
  differences (`$match` and upsert on rep1) are for them to confirm or fix.
