# 18 · Routines (recurring agentic tasks)

A customizable list of recurring tasks on a cadence — *Fill La Growth
Machine* (weekly), *Prepare the week* (weekly), *Monthly bookkeeping* — each
with an optional **agentic prep**. Two halves:

1. **The recurring list.** Each routine has a `cadence` (daily / weekly+weekday
   / monthly+day_of_month), an `area`, a `prep` recipe, and `last_done`.
   Due-ness is **computed** from the cadence and `last_done` — the current
   period's scheduled date, whether it's due, how overdue. No scheduler lives
   in the repo (rule 1); the view computes due-ness on read, and a **tick**
   stamps `last_done`. Fully editable (add / edit / activate).

2. **Prepare — the agentic part, rule-1-clean.** "Preparing" a routine has the
   app gather Aito-grounded data and fill a **prompt for Claude (Desktop, with
   the MCP tools)** to run — the app prepares, Claude executes. `prepare` itself
   runs no loop; the unattended **Auto-run** lane below executes the pack
   through the assistant's fenced loop. Recipes (`routines.py`):
   - `prospects` — the La Growth Machine case: pulls Aito-ranked candidate
     contacts (`who_to_call`) for the next outreach batch and writes a prompt
     ("draft openers via `opener_context`, build the import list…"). Every
     candidate and probability is Aito's.
   - `brief` — the week-prep prompt (defers to `prompts/week-prep.md`).
   - `none` — the routine's own prompt template, a plain reminder.

## Surfaces

- **Routines view** (NOW nav, beside Today): the editable list with cadence +
  due/overdue, a tick to mark the period done, a **Prepare** button that opens
  the run pack (candidates + the copyable Claude prompt), and a **Run ▶** button
  that executes the routine right now (the auto-run lane below) and shows the
  narration it wrote as a dated document.
- **Agent / CLI**: `routines_board`, `prepare_routine`, `tick_routine`,
  `run_routine` MCP tools; `log.add_routine` / `update_routine` /
  `tick_routine`; `company-ai load-routines`; `export routines` round-trips.

## Auto-run (scheduled)

`prepare` builds the pack; **`run_due` executes it.** For each *due* routine,
`routines.run_due` feeds the prepared prompt to the **dashboard assistant's
bounded, read-only tool loop** (`assistant.run_turn`, docs/16), records the
narration as a **dated document** (`noted_on`=run date, `topics=routine`; the
diary lane, docs/25 — the journal was retired into documents, `.ai/tasks/15`
Phase 2d), and **ticks** the routine. This is a scoped rule-1 exception — the
*same* fence as the assistant, invoked on a schedule instead of by a chat
message: the read-only Aito/web tools only, bounded rounds, narration-only, and
Aito still owns every number. No outbound action (that stays parked); the only
writes are the document note and the tick.

`run_due` runs every routine that is *due*; `run_routine(routine_id)` runs a
single one on demand and **defaults to `force=True`** — an explicit click/call
means run it now, even if it isn't due (the timer never forces). All three
triggers share the one executor and the one fence:

- **Timer** (unattended): `ops/routines-run.sh` +
  `ops/systemd/company-ai-routines.{service,timer}` (daily 06:00 Europe/Helsinki)
  — an **OS** timer, not an in-app scheduler (rule 1), mirroring `docs/15`. Runs
  the due ones only.
- **CLI**: `company-ai routines-run` (all due), `--only <ids>`, `--force`
  (re-run even if not due).
- **Dashboard**: the **Run ▶** button on each routine (force = an explicit click).
- **Agent**: the `run_routine` MCP tool (`force` defaults true).

All need `COMPANY_AI_LLM_API_KEY`; without it the run fails loudly. The
**Prepare** button and the Claude-Desktop path stay: auto-run is the unattended
lane, prepare-and-run-in-Claude the hands-on one — same pack.

## Not (yet) built

Routines don't auto-generate todos, and even the auto-run lane only *narrates*
into a document — it never sends, posts, or writes outbound (rule 1; parked).
Auto-materializing a due routine as a todo in its area is a clean, parked
extension.
