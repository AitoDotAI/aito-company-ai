# 19 · Extending it (add a table, a view, a routine)

This repo is a **reference implementation, not a configuration platform** — but
every table in it was added the same way, so extending it is a known path, not
an adventure. This is that path, as a checklist. (See `docs/01-architecture.md`
for the why, and the non-negotiable rules in `CLAUDE.md` for the must-nots.)

The mental model: **Claude reasons, Aito predicts, this repo is thin plumbing.**
A new entity is a table + the plumbing around it; a new prediction is an Aito
query, never a Python heuristic.

## Add a table (a new entity)

Worked examples to copy: `events` (a simple lifecycle table) and `materials` +
`channels` + `posts` (linked tables). Steps:

1. **Schema** — `src/company_ai/schema.py`: add the `FOO = {"type": "table",
   "columns": {...}}` dict and register it in `TABLES` (order matters when one
   table denormalizes from another — load the source first). Add any enums
   (`FOO_STATUS = {...}`) near the bottom. Nullable columns are addable to a
   live instance without a reload; non-nullable ones need a reload (see
   *Migration* below).
2. **Loader** — `src/company_ai/loaders.py`: write `parse_foo_row(row)` (validate
   loudly with `_require`; derive any computed columns) and `load_foo(client,
   data_dir)` (use `_reload`). Add `FOO_FILE`, and register in `TABLE_FILES`,
   `LOADERS`, and `LOAD_ORDER`. If the table has derived columns, list them so
   `export_table` drops them.
3. **Writes** — `src/company_ai/log.py`: `add_foo(...)` (reuse `parse_foo_row`),
   and for edits, a full-table-rewrite `update_foo` (Aito exposes no per-row
   id, so updates read-all → swap → `delete_table` + `create_table` + upload;
   copy `update_todo` / `log_deal_update`).
4. **Seed** — `scripts/generate_seed.py`: a `make_foo(...)` (deterministic — no
   `random` without the seeded `rng`); wire it into `generate()` and both call
   sites; `python scripts/generate_seed.py`.
5. **CLI / do** — `src/company_ai/cli.py`: a `load-foo` subcommand (+ add to
   `WRITE_CMDS`); add `load-foo` to the `./do seed` loop in `do`.
6. **API** — `src/company_ai/api.py`: read/write routes (`GET /api/foo`, `POST
   /api/foo`, …) wrapped in `_guarded`.
7. **MCP** — `src/company_ai/server.py`: `@mcp.tool()` wrappers so the agent
   gets the same surface as the dashboard.
8. **Tests** — `book/test_foo.py` (a booktest: print the request/response/
   derived output; cover the loud-failure cases); run `./do test` and accept
   snapshots. Update `book/test_loaders.py` and `book/test_privacy.py` (the
   file list + the `generate()` arity).
9. **Docs** — a `docs/NN-foo.md` and a pointer line in `CLAUDE.md`.

The moment a table is in `TABLES`, you get a lot for free: `create-schema`,
`doctor`, `migrate`, `export`/`load-all`, and the **Data sheet view** all work
on it with no extra code.

## Add a view (a surface)

`frontend/src/views.jsx` + `App.jsx`. Compose from the primitives in
`primitives.jsx` (`KpiRow`, `ActionPipeline`, `WeekCalendar`, `FunnelChart`,
`BarRow`, the `Block` wrapper) and fetch via helpers in `api.js`. Register the
view in the `VIEWS` map and add a nav entry to `NAV` in `App.jsx`. Add a
`data: [{table: "foo"}]` entry to get the Overview/Data tab for free. Cover the
component's client-only logic in `frontend/src/*.test.jsx` (`./do test-ui`).
Keep predictive numbers coming from the API — the view renders, it never
computes a ranking.

## Add a routine prep recipe

`src/company_ai/routines.py`: add a branch in `prepare()` and the recipe name
to `schema.ROUTINE_PREP`. A recipe gathers Aito-grounded data and returns a
**prompt for Claude to run** — it does not act itself (rule 1). Then any
operator can create routines using it from the UI, no further code.

## Conventions you cannot skip (CLAUDE.md)

- **Predictive logic lives in Aito**, never Python. Ranking/scoring/matching is
  a `_query` / `_predict` / `_match` call. If you're writing a heuristic in
  Python, move it into a query or park it.
- **No silent data handling** — unexpected input raises an assertion carrying
  the offending row. Never coerce or default past a surprise.
- **Booktest every behavior** — the request, response, and derived output are
  the snapshot a human reviews; a changed snapshot is the review artifact.
- **Privacy** — real data never enters the repo; seed is synthetic and
  byte-reproducible (the privacy booktest enforces this). Add new seed via the
  generator, not by hand.
- **The dashboard renders; it doesn't reason.** Writes are operator CRUD or
  agent/MCP; the only models inside the app are the two named exceptions in
  CLAUDE.md rule 1 (the board composer and the assistant).

## Migration (changing a live instance)

`company-ai doctor` (or `./do doctor`) shows drift; `company-ai create-schema`
(or `./do migrate`) adds missing tables/columns non-destructively. Adding a
nullable column is free. A **type/analyzer change** can't be altered in place
(Aito limitation, see `.ai/tasks/05`); that's a recreate+reload — `doctor`
flags it.

## Where it's deliberately not generic

The predictive recipes (`queries.py`, `scorer.py`, `funnels.py`,
`analytics.py`) and the domain enums are tuned to a one-person B2B sales-led
startup. That's the craft, and a fork is expected to rewrite them for its own
domain — like configuring an ERP. The plumbing above is what stays the same.
