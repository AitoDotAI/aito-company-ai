# 15 · The advisory board & the weekly rhythm

The morning brief is the daily loop. This is the weekly one: a Friday board
that evaluates the week and a Sunday session that prepares the next — both the
same shape as everything else here (a Claude session + MCP tools + a prompt),
just on a calendar instead of on demand.

## How it runs: inside the app, with a swappable LLM

The composer runs **server-side** — a small endpoint in the app
(`POST /api/board/run`, or `company-ai board-run`) that gathers the Aito
facts and asks an LLM to write the review. This is the scoped exception to
rule 1 (recorded there): the LLM is a *writer*, not an agent. It has no
tools, takes no actions, and — the hard line — never ranks, scores, or
predicts. Every number it writes is one Aito produced (`src/company_ai/board.py`
gathers them; rule 2 still owns all prediction). `src/company_ai/llm.py`
hides the provider, so **gpt-5-mini for testing becomes a high-end model
later by changing env only**. Two providers ship: `openai` (Bearer auth,
`model` in the body) and `azure` (Azure OpenAI: deployment-addressed URL,
`api-key` header, an api-version query param — a genuinely different wire
shape, which is why the abstraction exists).

    COMPANY_AI_LLM_PROVIDER=openai|azure    # blank => azure if an Azure URL is set
    COMPANY_AI_LLM_MODEL=gpt-5-mini         # label; swap to the high-end model later
    COMPANY_AI_LLM_API_KEY=...              # the composer's key (≠ Aito key)
    COMPANY_AI_LLM_BASE_URL=                # openai: blank = api.openai.com; set for a gateway
    # azure only:
    COMPANY_AI_LLM_AZURE_ENDPOINT=...       # https://<region>.api.cognitive.microsoft.com
    COMPANY_AI_LLM_AZURE_DEPLOYMENT=...     # the deployment name (selects the model)
    COMPANY_AI_LLM_AZURE_API_VERSION=...    # e.g. 2024-08-01-preview

**Already have Azure creds?** The config also reads the standard
`REACT_APP_OPENAI_*` names (`MODEL_URL` → endpoint, `MODEL_DEPLOYMENT` →
deployment, `MODEL_API_VERSION` → api-version, `MODEL_NAME` → model label,
`MODEL_API_KEY` → key), so dropping them in the env file is enough: the
provider auto-resolves to `azure` and only the key needs adding. The clean
`COMPANY_AI_LLM_*` names override them if both are set.

Running inside the app is also what makes scheduling tractable: the data
(Aito) and the model both live where the app runs, so a routine only has to
*trigger* it. A missing key raises loudly rather than composing nothing.

Why this still honours the spirit: the predictive intuition is unchanged —
it is Aito's, reached through the same queries the dashboard uses. We swapped
*who writes the prose* (a scheduled Claude session → an in-app LLM call), not
*where the reasoning about numbers lives*.

## The pieces (all in `prompts/`)

- **`board.toml`** — the configurable roster. By default five advisors:
  Sales/GTM, Marketing/Distribution, Product, Learning (Lean Startup), and the
  Chair (overall), who speaks last and synthesises. Each advisor is a *lens*
  with a mandate and the MCP tools it reads — edit the file to add, drop, or
  retune advisors; the next run honours it. An advisor advises; it never acts.
- **`board-review.md`** — the Friday review (commend the week's real wins,
  name the one change), closing with the Chair's one-screen verdict.
- **`week-prep.md`** — the Sunday plan for the upcoming week, honouring the
  protected calendar (Thursday Sisua, Wednesday-morning deep work) and the
  weekday rhythm, ending in next week's shape, call-queue seeds, deals to
  push, bets to run, and what to ship.

## The Advisory panel (the board as personas, in the dashboard)

The Friday review composes **one** synthesised document. The **Advisory panel**
is the same doctrine turned into a *board you can see*: each roster advisor
reflects **in its own voice**, from its own reads, as a separate composition —
so a `persona` comes through. It's the **Advisory** view under Knowledge
(`frontend/src/views.jsx`), backed by `board.panel()` and:

- `GET /api/advisory` — the last saved panel (or empty).
- `POST /api/advisory/run` — reflect now (a handful of LLM calls; the button
  shows a spinner). Also `company-ai advisory`.

It runs **on demand** (the "Reflect now" button) and **weekly** (the same
Friday timer can call `company-ai advisory`). Output is saved to `.briefs/`
(gitignored — real analysis stays out of the repo) so the view shows the
latest without re-running; the Chair speaks last and synthesises the others.

**Personas make it a named board.** Give an advisor a `persona` and it speaks
in that figure's voice — ship-shape defaults wire Eric Ries (Learning) and
Paul Graham (Chair); set your own for any seat. The persona changes only the
*voice*: the mandate, the reads, and the hard rules are unchanged, and every
number is still Aito's (rule 2). An advisor with no persona is the neutral
role voice.

## Where the roster lives: Aito, seeded from board.toml

The roster is **config stored in an Aito `advisors` table**, so it can be
retuned at runtime — **no redeploy**. `prompts/board.toml` is the seed and the
default: `board.load_roster(client)` reads the table when it's populated, and
falls back to `board.toml` when it isn't (a fresh instance, or one predating
the table). So a clone still works from the file, and a running app is edited
live.

Two ways to maintain it, both operator-directed (the *read-only* dashboard
assistant, rule 1b, does **not** write it):

- **Your Claude sessions, over MCP** — `add_advisor`, `update_advisor`,
  `remove_advisor` (the same way todos/routines are maintained). "Add a
  finance advisor voiced as Bill Gurley reading the pipeline" is one call.
- **The dashboard** — the Advisory view's **+ Advisor** and per-card editor
  (pencil) write the same rows. `reads` are picked from `board.READS`; an
  unknown read or a duplicate id is refused (rule 3).

The table is `advisors` (schema.py): `advisor_id, name, persona, mandate,
reads, rank, active`. It is **config, not CSV data**, so it sits outside the
export/load-all/migrate machinery (`load_advisors` seeds it from `board.toml`;
a migrated instance re-seeds from the file — persist roster changes you want to
keep to `board.toml`). The first edit on an un-seeded instance materialises the
default roster first, so an edit never silently drops the other advisors.

## The rhythm (Europe/Helsinki)

Each event has a **preparation run ≥24h before** it, so the live session is
grounded and the operator can correct course first. Four routines:

| When            | Routine                  | Mode      |
|-----------------|--------------------------|-----------|
| Thursday 16:00  | board prep               | `prepare` |
| Friday 16:00    | board review             | `board`   |
| Saturday 16:00  | week-prep                | `prepare` |
| Sunday 16:00    | week plan                | `plan`    |

The `prepare` runs draft to `.briefs/` (gitignored — real pipeline analysis
never enters the repo) and ping the operator to review/edit; the live runs
fold in those edits, refresh the numbers, and deliver the final.

## Setting it up

The runs are triggered on a schedule that invokes the composer with a prompt
+ mode — `company-ai board-run board-review.md --mode board`, or
`POST /api/board/run?prompt=board-review.md&mode=board`. The trigger needs no
intelligence of its own; the app gathers and composes.

Because the composer runs in-app on the operator's host (local Aito, local
LLM key), the scheduler is **local**, not a cloud routine (a cloud agent
can't reach localhost). The shipped setup is `systemd --user` timers:

- `ops/board-run.sh <prompt> <mode>` — the entry point. Self-locating; enters
  the same Nix shell `./do` uses, defaults `COMPANY_AI_ENV=.env.aito`.
- `ops/systemd/company-ai-*.{service,timer}` — the four units (board-prep
  Thu, board Fri, weekprep Sat, weekplan Sun; all 16:00 Europe/Helsinki).

Install / inspect / stop:

    cp ops/systemd/company-ai-*.{service,timer} ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now company-ai-{board-prep,board,weekprep,weekplan}.timer
    systemctl --user list-timers 'company-ai-*'        # next fire times
    systemctl --user disable --now company-ai-board.timer   # stop one

**Prerequisite:** the target env file (`.env.aito`) must have a live Aito
instance *and* `COMPANY_AI_LLM_API_KEY` set, or a fired run fails loudly
(logged to the journal: `journalctl --user -u company-ai-board.service`) and
composes nothing — by design. A cloud trigger is only viable once the app is
deployed at a URL the cloud can reach.
