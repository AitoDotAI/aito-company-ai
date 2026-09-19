# Contributing

This is a one-person company's sales agent: **Claude reasons, [Aito](https://aito.ai)
predicts, this repo is thin plumbing** (schema, loaders, an MCP server, a
read-only-ish React dashboard, prompts, tests). It's a *reference
implementation* — opinionated for a solo B2B sales-led startup. Forking and
adapting it to your own entities is the intended model (it's a bit like an
ERP: every company's needs differ). The plumbing stays; the domain bits you
rewrite.

## Setup

A fresh clone reaches a seeded dashboard in minutes:

```
./do install          # uv sync + npm install
docker start <your local aito container>   # or run one; see README
./do seed             # create schema + load synthetic data/seed/
./do start            # dashboard on :8770   (./do dev for hot-reload)
```

`COMPANY_AI_ENV=.env.<name>` selects the instance (`.env.local`, `.env.aito`,
…). `./do doctor` reports schema drift; `./do migrate` fixes it
non-destructively. Full quickstart in the README.

## Tests

- **Backend:** `./do test` — review-driven [booktests](https://github.com/lumoa-oss/booktest).
  A changed snapshot is the review artifact; accept with `uv run booktest -a`
  after eyeballing the diff.
  - **The suite reseeds** (`create_schema` drops and recreates tables), so it
    runs only against a **dedicated test env**. Create a `.env.test` pointing
    `AITO_INSTANCE_URL` at a throwaway Aito env whose path contains `booktest`
    or `test` (e.g. `…/env/booktest`, or a local container). `book/__booktest__.py`
    forces the suite onto `.env.test` and **refuses to run against anything
    else** (production included) — no override; the guard is the point. Leave
    `COMPANY_AI_DATA_DIR` unset there so the private dataset can't be loaded.
- **Frontend:** `./do test-ui` — Vitest over the client-only logic.

Run both before a PR that touches queries, schema, loaders, or views.

## The non-negotiable rules

Read [`CLAUDE.md`](CLAUDE.md) — it's short and it's the law. In brief:

1. **No agent framework.** Reasoning is a Claude session over MCP, not a loop
   in the repo. (Two named, fenced exceptions: the board composer and the
   dashboard assistant.)
2. **All predictive logic lives in Aito queries** — ranking/scoring/matching
   is `_query`/`_predict`/`_match`. A Python heuristic is a bug.
3. **No silent data handling** — surprising input raises, carrying the row.
4. **No inference-touching change without a numerical test first.**
5. **Booktest is the harness** — every behavior ships with a reviewed snapshot.

Plus: **real data never enters the repo** (synthetic seed only — `docs/06-privacy.md`).

## Adding things

Adding a table, a view, or a routine recipe is a known checklist —
see [`docs/19-extending.md`](docs/19-extending.md). The full spec set is in
[`docs/`](docs/) (architecture, schema, the predictive funnels, the dashboard,
the action surface, deals, experiments, the board, the assistant, …).

## Commits

Small, single-purpose, plain descriptive messages — no "wip", no emoji. Work
as if a stranger will read both the code and the process that produced it.
