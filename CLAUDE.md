# CLAUDE.md

Operating instructions for any Claude session working in this repository.
This file is public by intent. Work as if a stranger will read both the code
and the process that produced it, because one day they might.

## What this is

A one-person company's sales agent whose intuition is a predictive database.
Claude is the reasoning layer; [Aito](https://aito.ai) is the statistical
layer; this repo is the thin plumbing between them: schema, loaders, an MCP
server, a morning-brief prompt, a read-only dashboard app (React over a
FastAPI contract the agent shares via MCP), and tests. It runs a real
pipeline daily.

## The architecture, in one sentence

The morning brief is three MCP calls and a prompt.

That sentence is the review test for the *brief*: if the brief can no longer
be described that way, it has overgrown and should be cut back, not
documented around. The dashboard sits alongside it as a read-only window on
the same Aito queries — it adds a view, never a third place where reasoning
lives. Full design in `docs/01-architecture.md`.

## Non-negotiable rules

1. **No agent framework.** No LangGraph, LangChain, custom agent loops, or
   schedulers. The reasoning layer is a Claude session calling MCP tools,
   never a framework standing in for it. This repo ships plumbing, not
   intelligence. Read-only presentation surfaces are fine and encouraged —
   the Segment 360 dashboard (`docs/07-dashboard.md`) is a small read-only
   web server that renders Aito query results; what stays banned is
   anything that *reasons* or *acts* outside Claude and Aito.
   **Three scoped exceptions, all operator-directed and behind the swappable
   provider in `src/company_ai/llm.py`:**
   (a) the weekly week-prep *composer* (`docs/15-week-prep.md`,
   `src/company_ai/board.py`) — a writer with no tools and no autonomy, turning
   Aito's outputs into Sunday-prep prose;
   (b) the dashboard *assistant* (`docs/16-assistant.md`) — a right-side
   chat that does run a bounded, server-side tool-calling loop, so it is an
   agent loop and is named as such. It is fenced hard: it may call **only**
   the read tools in `src/company_ai/assistant.py` — most are existing
   Aito-backed queries (the same functions MCP and the dashboard use, no new
   logic, no writes); the exceptions are two read-only web tools, `web_search`
   (`websearch.py`) and `fetch_page` (`webfetch.py`, SSRF-guarded), for
   *external* facts Aito can't hold (docs/16) — still narration-only and still
   barred from computing any number. The loop is bounded; and rule 2 still
   owns every internal number. The model chooses *which* tool and narrates the result; it never
   computes a ranking, score, or prediction itself.
   (c) the *routines runner* (`routines.run_due`, `docs/18-routines.md`) — an
   OS timer (`ops/company-ai-routines.*`, **not** an in-app scheduler) that,
   for each *due* routine, runs its prepared prompt through **exactly** the
   assistant loop of (b) — same fence, same read-only tools, same bounds —
   and records the narration as a dated document (the diary lane, docs/25; the
   journal was retired into documents, docs/15 Phase 2d). It is (b) invoked on a
   schedule instead of by a chat message: no new tools, no writes beyond the
   document note + the routine tick, and no outbound action (that stays
   parked). These are the only places a model runs inside the app; anything
   beyond them (writes from the assistant, outbound from a routine, a further
   surface) is parked, not built.
2. **All predictive logic lives in Aito queries.** Ranking, scoring,
   weighting, similarity, and pattern matching are `_query`, `_predict`,
   `_match`, and `_similarity` calls. Python may load data, call Aito,
   format results, and assert invariants. If you are writing a heuristic in
   Python, stop and move it into a query. If it cannot be expressed as a
   query, propose it in an issue or task note instead of implementing it.
3. **No silent data handling.** Unexpected input (missing field, malformed
   row, unknown enum value) raises an assertion that includes the offending
   row. Never skip, coerce, or default your way past surprising data; the
   surprise is the information.
4. **No new inference-touching code without a numerical correctness test
   that exists first.** Performance metrics alone are not acceptance:
   a change is judged by before/after prediction output on the seed data.
5. **Booktest is the harness.** Every behavior ships with a booktest that
   prints the Aito request, the response, and the derived output, snapshot-
   reviewed by a human. If a change alters a snapshot, the diff is the
   review artifact, not an inconvenience.

## Working agreement (autonomy)

- **Inside the specs in `docs/`, proceed without asking.** Implement, test,
  and commit in small, single-purpose commits with plain descriptive
  messages. No "wip", no "fixes", no emoji.
- **Outside the specs, propose and park.** Write the proposal as a short
  note in `.ai/tasks/`, do not build it. This explicitly covers: Head 2
  (external support agent), any outbound automation (email sending,
  LinkedIn, calendar writes), and new decision domains. Read-only
  reporting surfaces (dashboards, exports) are in scope, not parked.
- **When blocked, say so plainly** in the task note: what was attempted,
  what failed, the exact error. Do not stack workarounds on top of
  unimplemented or misbehaving functionality; expose the root cause.
- **Honest output beats impressive output.** Early predictions from small
  data will be weak. Show the calibrated `$p` anyway. Weak-and-honest is
  the product working as designed; confident-and-fabricated is a defect.
- Budget discipline: when a phase overruns its estimate in
  `docs/05-phases.md`, cut features from the phase. Never extend silently.

## Testing discipline

`docs/04-testing.md` is the spec. Summary: review-driven booktests against
`data/seed/`, plus a deliberately tiny dataset to keep cold-start behavior
honest. The round-trip test is sacred: logging an outcome must visibly
change the next brief. Run the suite before any commit that touches
queries, schema, or loaders.

## Privacy

Real pipeline data never enters this repository. The repo ships synthetic
seed data only; the real dataset lives outside the tree at a path supplied
by environment variable. Details and the pre-commit check are in
`docs/06-privacy.md`. When in doubt, grep before you commit.

## Definition of done (Head 1)

A fresh clone plus a local Aito container reaches a working seeded morning
brief in under ten minutes, following only the README. All booktests pass
and have been human-reviewed. The brief fits one phone screen. No real
names, numbers, or non-public company data anywhere in tracked files.

## Pointers

- Specs: `docs/` (overview, architecture, schema, brief, testing, phases, privacy, dashboard, two-sides, funnels, messaging-formula, dashboard-app, todos-and-now)
- Using it, both sides: `docs/08-two-sides.md` (agent over MCP + human dashboard)
- Predictive funnels (sales + website/acquisition): `docs/09-funnels.md`
- Dashboard app (React + FastAPI, the shared contract): `docs/11-dashboard-app.md`
- Action surface (todos + the Now view): `docs/12-todos-and-now.md`
- Deals pipeline + close-likelihood + the closed loop: `docs/13-deals.md`
- Experiments (the learning pipeline, Build-Measure-Learn): `docs/14-experiments.md`
- Week-prep composer (the Sunday-prep writer; grounded, tool-less, LLM prose over Aito facts; `board-run` CLI + `ops/board-run.sh`): `docs/15-week-prep.md`
- Dashboard assistant (right-side chat; bounded Aito-backed tool loop): `docs/16-assistant.md`
- Events to attend (go/no-go board + calendar): `docs/17-events.md`
- Routines (recurring agentic tasks; prepare → Aito candidates + a Claude prompt): `docs/18-routines.md`
- Journal (RETIRED — folded into Documents' `noted_on` diary axis, docs/25; see Phase 2d): `docs/20-journal.md`
- Backups & restore (Aito env snapshots; daily×7 + tx×16, guarded restore): `docs/21-backups.md`
- Change log (append-only audit of created/updated/done/won/lost; Activity view + `recent_changes`): `docs/22-changelog.md`
- Smart search (unified `search_items` index over content; Aito text-match ranking trained by clicks via the impressions loop; Search view + `smart_search` + MCP `search`/`record_click`): `docs/23-search.md`
- Documents (the knowledge store; Aito `documents` collection, kind{docs,internal}+area tags, company/person links, in-dashboard editor, area-view Documents tabs; replaces the read-only file "Library"): `docs/25-documents.md`
- Remote MCP (the stdio MCP server exposed over HTTP at `/mcp` for cloud Claude; bearer-gated + fail-closed, read+safe-writes surface, mounted in the dashboard app): `docs/26-remote-mcp.md`
- Users & assignees (solo → small team; `users` collection {operator,sdr}, `assignee` on contacts/todos/deals, identity from Entra Easy Auth header → My work; auth is not app code; role enforcement in the `role_guard` middleware): `docs/27-users-and-assignees.md`
- API tokens (named, revocable bearer tokens for the remote MCP; SHA-256 hash-at-rest, plaintext shown once, operator-only Admin UI, `tokens.verify` accepts env master or an active named token): `docs/28-tokens.md`
- Remote MCP OAuth (self-hosted OAuth 2.1 AS for claude.ai's connector; SDK serves `/authorize`+`/token`+`/register`+`.well-known`, we implement the in-memory provider `mcpoauth.py`; `/authorize` behind Easy Auth is the real gate; one `/mcp` gate accepts OAuth **and** bearer tokens; `COMPANY_AI_PUBLIC_URL` turns it on): `docs/29-remote-mcp-oauth.md`
- Knowledge graph (facts harvested onto the company node + link traversal:
  forward `company_id.industry`, reverse `$refs.contacts.company_id`; the
  Knowledge graph view shows each question beside the query that answered it):
  `docs/31-knowledge-graph.md`
- Extending it (add a table / view / routine — the checklist): `docs/19-extending.md`; contributor setup in `CONTRIBUTING.md`
