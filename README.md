# Company AI

**A small company's sales assistant that learns from what actually happened.**

It keeps track of the things a salesperson otherwise keeps in their head —
who the customers are, which deals are moving, who was in the last meeting,
what was said — and answers questions about them.

What makes it different from a normal CRM is where the numbers come from.
Nobody configures a scoring rule. Every rate, ranking and likelihood is
worked out from **this company's own history**, so when the history changes
the answers change by themselves. A deal looks promising because deals that
looked like it were won before.

[![Overview](docs/assets/dashboard-overview.png)](docs/use-cases/README.md)

*The Overview screen, on this repository's public demo data — invented
companies, invented people, no real contacts anywhere.*

**→ [Take the tour](docs/use-cases/README.md)** — what it does, one screen at
a time, in pictures.

## The kind of question it answers

- **Who should I call today, and what do I say?** Ranked by who is most
  likely to move, with the reason attached.
- **Which of these deals will actually close?** A probability for every open
  deal, learned from the ones that closed before — next to your own guess,
  because where the two disagree is the deal worth looking at.
- **Who actually pays us, and what are they worth?** Customers, prospects and
  lapsed accounts, with what each brings in.
- **Where is the funnel leaking, and what should I post?** The stage costing
  the most, and how a draft is likely to do before you publish it.
- **What do we already know about this account?** Notes and meetings filed
  against the company and the people, not in a folder someone has to find.
- **What kind of company is this, judged only by who works there?** Accounts,
  people, deals and notes are linked, so a question can be answered from an
  account's *neighbourhood* rather than from its own record.
- **Where did we discuss pricing?** — asked in Finnish, over notes written in
  English. Search matches on meaning as well as words, so a result need share
  no term with the question.

It is honest when it does not know. Early on, with little history, the
probabilities are weak and look weak. A confident number from four data
points would be the bug, not the feature.

## Two ways to use it

**As a conversation.** Ask in plain language — the assistant answers from the
same data, and shows which query produced each number, so an answer can
always be checked rather than trusted.

**As a dashboard.** A set of read-only screens over the same numbers, for
when you want to look rather than ask.

## Try it

You need [Docker](https://www.docker.com/) and about a minute. This loads the
invented demo data, not anything real:

```sh
docker run -d -p 9005:9005 ghcr.io/aitohq/aito   # the database
cp .env.example .env                             # point at it
./do install && ./do seed && ./do start          # → http://localhost:8770
```

---

## How it works

The rest of this file is for people who want to run or change it.

Claude does the reasoning; [Aito](https://aito.ai) — a predictive database —
does the ranking, retrieval and the probabilities; this repository
is the thin layer between them. It holds schema, loaders, an MCP server, a
morning-brief prompt, a read-only dashboard, and the tests. It runs a real
pipeline daily.

The operational pattern behind [agent.aito.ai](https://agent.aito.ai), run on
our own pipeline. The morning brief is three MCP calls and a prompt.

```
Claude session (Code or Desktop)     reasoning: composes the brief,
        |                            drafts openers, takes log commands
        |  MCP (stdio)
        v
aito-company-ai MCP server           thin tool layer, zero logic
        |  HTTP
        v
Aito instance (docker)               intuition: ranking, similarity,
        ^                            probabilities, learning
        |
   loaders (CLI)                     rolodex + outcome log -> Aito tables
```

## Setup (shared)

One Aito instance is the brain; both sides below read the same tables.

```sh
docker run -d -p 9005:9005 ghcr.io/aitohq/aito        # 1. an Aito instance
cp .env.example .env                                   # 2. point at it
./do seed                                              # 3. schema + every table
```

`./do seed` runs `create-schema` and then `load-all`, which walks
`loaders.LOAD_ORDER` and loads every table whose CSV is present. Listing the
loads by hand here is how this drifted before: the list named six tables while
the seed had fifteen, so a fresh clone came up with an empty Routines view and
no users while looking complete. To load your own data instead of the
synthetic set, point it at a directory of CSVs with
`company-ai load-all --dir <dir>`.

Then pick a side — most days you use both. Full guide:
[`docs/08-two-sides.md`](docs/08-two-sides.md).

## Side 1 — the agent (Claude over MCP)

For running the call window: who to call now, the opener, what changed,
and logging each result in a sentence.

```sh
claude mcp add aito-company-ai -- uv --directory "$PWD" run company-ai-mcp
```

To target a specific instance, pass its env file:
`-e COMPANY_AI_ENV=.env.aito`. For all your projects, add `-s user`. On a
**nix** host, if the server fails to start (`cannot import name 'Sentinel'`),
a leaked py3.11 `PYTHONPATH` is the cause — prefix the command with
`env -u PYTHONPATH`:
`claude mcp add aito-company-ai -- env -u PYTHONPATH uv --directory "$PWD" run company-ai-mcp`.

Restart the session, then ask for the morning brief using
`prompts/morning-brief.md`. The agent has tools for the brief
(`who_to_call`, `opener_context`, `what_changed`), the analytics
(`segment_360`, `funnel`, `score_post`, `deal_pipeline`, `todos_now`),
writing (`log_touch`, `log_decision`, `log_deal_update`, `complete_todo`),
and ingest (`add_contact`, `add_deal`), plus a `populate` prompt. Log a
result by sentence, or:

```sh
uv run company-ai log <contact_id> call 0800 no_answer
uv run company-ai brief --no-llm     # the brief without a model in the loop
```

## Side 2 — the human (the dashboard app)

A React app over a FastAPI backend — the same `/api/*` contract the agent
reaches via MCP, rendered for a human. Read-only: every number is an Aito
query.

The `./do` script manages it (run `./do help` for all commands):

```sh
./do install            # uv sync + npm install (one-time)
./do seed               # create schema + load every table from data/seed
./do start              # build + serve in the background → http://localhost:8770
./do status             # is it up? which instance, which build
./do restart            # rebuild + restart    ./do stop    ./do logs
./do dev                # vite hot-reload (:5173) + backend (:8770), for UI work
./do reindex            # rebuild the search index (+ embeddings, if configured)
```

`./do` targets the Aito instance in `COMPANY_AI_ENV` (defaulting to
`.env.local` when present, so `./do seed` never drops tables on a real
instance by accident). Under the hood it's `uv run company-ai dashboard`
serving the built `frontend/` bundle.

The shell follows a fixed information architecture — **Now · Work (Sales,
Marketing, Operations, R&D) · Knowledge · Analytics** — and every view is
composed from shared primitives (`kpi-row`, `chart`, `optimizer`,
`action-pipeline`, `action-calendar`). It opens on **Now**: the most urgent
actions across every area, action-first.

![Now — the action-first landing view](docs/assets/dashboard-now.png)

Each Work view opens with its action block (Sales/Marketing by date,
Operations/R&D by priority), then its analytics. Spec:
[`docs/12-todos-and-now.md`](docs/12-todos-and-now.md). **Sales** also shows
the pipeline: each open deal's weighted value with Aito's
close-likelihood next to the operator's own probability — where they diverge
is the deal to look at ([`docs/13-deals.md`](docs/13-deals.md)).

![Sales analytics — pipeline by stage, Aito close-likelihood, the win-rate trend, and who to reach](docs/assets/dashboard-sales.png)

The **Documents** view is the knowledge store the agent grounds on — the
operator's strategy, plans, and notes as a first-class Aito collection, tagged
by kind and area, linked to companies and people, edited in place, and searchable
([`docs/25-documents.md`](docs/25-documents.md)). Import an existing markdown
dir once with `company-ai documents-import <dir>`.

![Documents — notes linked to the accounts and people they concern](docs/assets/dashboard-documents.png)

The **Knowledge graph** view is the newest surface. Contacts, deals and
documents all link to the company, and Aito walks those links in both
directions — forward to the account (`company_id.industry`), and back to its
people (`$refs.contacts.company_id`). Each card is a single query, shown next
to its answer, because the claim being made is that the question and the query
are nearly the same sentence.

[![Knowledge graph — each question beside the query that answered it](docs/assets/dashboard-graph-hero.png)](docs/31-knowledge-graph.md)

Two of those cards do something a relational database cannot: infer an
account's industry from the people linked to it, and predict a deal's outcome
from a fact that exists nowhere on the deal — returning `$why`, so the answer
arrives with what moved it and by how much. Design, and the sharp edges found
building it, in [`docs/31-knowledge-graph.md`](docs/31-knowledge-graph.md).

**Search** ranks documents, contacts and deals together, and learns: results
that get clicked for a query rise for similar queries later. With an
embeddings deployment configured it also matches on meaning, which is what
lets a French or Finnish question find an English note
([`docs/23-search.md`](docs/23-search.md)).

![Search — a French query returning English documents](docs/assets/dashboard-search-semantic.png)

**Analytics — Segment 360.** Pick a slice (segment · tier · ai_lifecycle ·
source); each KPI shows the rate, the root causes (`_relate`), and the lever
(`_recommend`). Design in [`docs/07-dashboard.md`](docs/07-dashboard.md).

![Analytics — Segment 360](docs/assets/dashboard-analytics.png)

**Marketing** combines the website/acquisition funnel (visitor → signup →
trial → paid, with the biggest-drop leak and Aito's outlook) and
the **post scorer** — the messaging formula that predicts a draft's win
probability on its channel (LinkedIn reach / HN views, never upvotes) and the
lever to switch.

![Marketing — this week's plan and the posts to ship, with the funnel and post scorer below](docs/assets/dashboard-distribution.png)

Specs: [`docs/09-funnels.md`](docs/09-funnels.md),
[`docs/10-messaging-formula.md`](docs/10-messaging-formula.md). The dashboard
architecture is in [`docs/11-dashboard-app.md`](docs/11-dashboard-app.md).
(Screenshots are synthetic seed data — no real contacts.)

## Privacy split

The repo tracks code and **synthetic** seed data only (generated by
`scripts/generate_seed.py`, fictional namespace, no phone numbers or email
addresses anywhere — only `phone_present`/`email_present` booleans). The
real rolodex lives outside the tree at `COMPANY_AI_DATA_DIR`; loaders read
it at runtime. Details in `docs/06-privacy.md`.

## Permissions

The agent is internal-facing: it reads the pipeline and drafts text for a
human to act on. It sends nothing outbound — no email, no LinkedIn, no
calendar writes; those are gated decisions, not features (see
`docs/05-phases.md`). Outcome logging is the only write, and it is always
operator-initiated.

## Tests

```sh
uv run booktest book          # review-driven snapshots, see docs/04-testing.md
```
