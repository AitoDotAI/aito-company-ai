# Company AI

**An open-source agentic OS for a small company.** Sales, marketing, R&D and
everything the company knows live in one database that learns from its own
history. AI agents work in it the way a team would — filing tasks, recording
decisions, writing notes — and anyone can ask it what to do next and get an
answer grounded in what actually happened.

[![Overview](docs/assets/dashboard-overview.png)](docs/use-cases/README.md)

*The Overview screen on the public demo data — invented companies, invented
people.*

**[Take the tour →](docs/use-cases/README.md)** &nbsp;·&nbsp;
**[Run it in ten minutes ↓](#try-it)** &nbsp;·&nbsp;
**[Make it yours ↓](#make-it-yours)**

## What it answers

**Going to market**

- **Who should I call today?** Ranked by who is most likely to move, with the
  reason attached.
- **What is in the pipeline, and what has gone quiet?** Deals by stage and
  value, how long each has been cold, and a close-likelihood learned from the
  deals that closed before.
- **Where is the funnel leaking, and which channel works for this material?**
  The stage costing the most, and how the same piece did in each place it ran.

**Building and learning**

- **Did that experiment pay off?** What was tried, what was expected, what
  happened — and a logged outcome visibly moves the next answer.
- **What did we decide, and did it hold up?** Decisions kept with their
  outcomes, including the ones where the recommendation was overruled.
- **What is R&D working on, and what is late?** The same action list as sales,
  ranked by priority instead of by date.

**Knowing**

- **Everything we have on this person and this company.** One search across
  notes, contacts and deals, ranked by relevance and sharpened by what people
  click.
- **What kind of company is this, judged by who works there?** Accounts,
  people and deals are linked, so a question can be answered from an account's
  neighbourhood rather than from its own record.

Alongside those: events as a go/no-go board, recurring work that prepares
itself, and a log of everything that changed.

## Why it works differently

**The numbers come from your history, not from rules.** Nobody configures a
lead score. Every rate, ranking and likelihood is learned from what this
company has already done — by [Aito](https://aito.ai), a predictive database —
so when the history changes, the answers change with it.

**Agents work in it, not just read it.** Twenty-eight of its tools write: agents
file and claim tasks, record decisions, log outcomes, add notes, contacts and
deals. Several can work at once, which is why claiming a task before starting
it is part of the protocol.

**Answers show their working.** The assistant lists the tool calls behind every
reply, and the knowledge graph shows the exact query behind each card, so an
answer can be checked rather than taken on trust.

**Prediction proposes; people decide.**

> **Prediction may propose, with its reasons attached. Only a deterministic
> check or a named human writes state.**

A ranked shortlist someone confirms is cheap when it is wrong; a field a model
filled in is not. So approvals, ownership and measured numbers stay with people
and hard checks, and the model's job is to put the right three things in front
of someone.

## What it deliberately does not do

- **It does not send anything.** No email, no LinkedIn, no calendar invites.
  Agents draft; a person sends.
- **It does not let a model decide.** Predictions are suggestions with reasons;
  approvals and ownership are deterministic or human.
- **It does not fake confidence.** Search and linking work as soon as there is
  data. Forecasts such as close-likelihood need enough closed deals behind
  them, and say so plainly until they have them.
- **It is not a hosted service, or built for a large sales floor.** One small
  company, one instance, run by you: a database container and this repository.
- **It is not an agent framework.** The reasoning is a Claude session, the
  statistics are Aito, and this repository is the thin layer between them.

## Make it yours

It ships speaking our language — our customer segments, our reasons deals
stall, our working week. Each of those is a setting, not code:

- **Your vocabulary, in one file.** Customer segments and tiers, why deals
  stall, where you publish, which job titles count as technical, your call
  times and when you are unavailable. → [`docs/32`](docs/32-deployment-vocabulary.md)
- **Your data, checked before it loads.** `./do validate` reads an export and
  lists every problem at once, grouped into the handful of fixes it really is —
  no database needed.
- **Your own tables, views and routines.** The data model is the product, and
  extending it is a [checklist](docs/19-extending.md).

The same pattern fits anything shaped like *records, outcomes, and a question
you would like answered from them*: support tickets and what resolves them, a
recruiting pipeline and who accepts, a partner programme and which partners
deliver.

## Try it

You need [Docker](https://www.docker.com/) and about ten minutes. This loads
the invented demo data, not anything real:

```sh
git clone https://github.com/AitoDotAI/aito-company-ai && cd aito-company-ai
docker run -d -p 9005:9005 -e AITO_DISABLE_AUTH=true ghcr.io/aitohq/aito
cp .env.example .env
./do install && ./do seed && ./do start      # → http://localhost:8770
```

The demo data is dated June 2026, and the dashboard says so: everything is
measured from that date, so you see a working week rather than a backlog.

**With your own data**, after describing your vocabulary in a JSON file and
pointing `COMPANY_AI_VOCABULARY` at it in `.env`:

```sh
./do validate path/to/your/export        # every problem at once
SEED_DIR=path/to/your/export ./do seed   # then load it
```

To ask in plain language, connect a Claude session to the MCP server —
[Side 1](#side-1--the-agent-claude-over-mcp) below. Semantic search (a
misspelled name, or a question in Finnish over notes written in English) is
optional and needs an embeddings key — see `.env.example`.

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
docker run -d -p 9005:9005 -e AITO_DISABLE_AUTH=true ghcr.io/aitohq/aito        # 1. an Aito instance
cp .env.example .env                                   # 2. point at it
./do seed                                              # 3. schema + every table
```

`./do seed` runs `create-schema` and then `load-all`, which walks
`loaders.LOAD_ORDER` and loads every table whose CSV is present. Listing the
loads by hand here is how this drifted before: the list named six tables while
the seed had fifteen, so a fresh clone came up with an empty Routines view and
no users while looking complete. To load your own data instead of the
synthetic set, check it with `./do validate <dir>`, then
`SEED_DIR=<dir> ./do seed`. Going through `./do seed` rather than a bare
`load-all` matters: it is what clears the demo's reckoning date, so your data
is measured from today and not from June 2026.

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

The agent is internal-facing, and inside that boundary it writes freely: todos,
decisions, outcomes, touches, notes, routine ticks, contacts, deals,
experiments, events and posts all have write tools, and agents use them heavily
— the board is largely agent-written. Several agents work the same store
concurrently, which is why claiming a todo before starting it is a protocol
rather than a nicety (`docs/12-todos-and-now.md`).

The boundary is OUTBOUND action: no email, no LinkedIn, no calendar writes.
Those are gated decisions, not features (see `docs/05-phases.md`). An agent
may draft the message; a human sends it.

Restoring a backup is also operator-only: MCP can snapshot, never promote
(`docs/21-backups.md`).

## Tests

```sh
uv run booktest book          # review-driven snapshots, see docs/04-testing.md
```
