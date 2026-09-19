# Deals: the pipeline and close-likelihood

The `deals` table is the sales pipeline (architecture spec §2.1). Open deals
are the current pipeline; closed deals (won/lost) are the substrate Aito
learns close-likelihood from. The Sales view shows the weighted pipeline and,
per open deal, **how likely it is to close and why** — with the operator's
own probability next to Aito's, because where they diverge is the signal.

## What the pipeline reports

`deals.pipeline` (the data layer), all from Aito except deterministic
arithmetic:

- **KPIs** — weighted pipeline (Σ value × the operator's probability), open
  value, open-deal count, stalled count. Plain arithmetic over the open
  deals (formatting, not inference).
- **Per open deal** — Aito's **close-likelihood**: `_predict won GIVEN
  stage, blocker, champion_present` over the closed-deal history, with the
  `$why` (which feature drives it). Plus a **stalled** flag (no touch in
  > 14 days) — deterministic.

The planted signal the model recovers: a present champion and no blocker
win; no champion, a blocker, and a long touch gap lose. So a deal the
operator rates 70% but which looks like deals that historically closed at
20% (no champion, still a lead, stalled) is surfaced as exactly that — the
calibrated second opinion.

## The closed loop

Sales todos link to a deal (`linked_type=deal`, see `docs/12`). When a
deal-linked action resolves, `complete_todo` marks the todo done *and* calls
`log_deal_update` to advance the deal in one step — the pipeline re-ranks and
the risk model re-derives immediately. `log_deal_update` is also callable on
its own (a stage move with no todo). Because Aito exposes no per-row id, the
update rewrites the (small) deals table: read all, swap the one row, reload —
idempotent, no duplicate `deal_id`s. This is the deals analog of the sacred
touch round-trip; `book/test_deals.py` proves the deal write and
`book/test_todos.py` proves the full todo→deal loop.

These are the only deal writes, and (like every write) operator- or
agent-initiated, never automatic. The agent uses the `complete_todo`,
`log_deal_update`, and `deal_pipeline` MCP tools; the dashboard stays
read-only.

## The data

`deals` schema in `docs/02-schema.md`. Loaded by `company-ai load-deals`
(`--seed`, or real data via `COMPANY_AI_DATA_DIR/deals.csv`). `won` is
derived from `stage` at load (closed_won → true, closed_lost → false, open →
null). Seed is synthetic (no PII); real deals — company names, values,
champions — live only in the private dataset.

## Not modelled yet

Expected close date and deal age as predictor features; multi-contact deals
(a deal currently links to a company and optionally a contact via a todo,
not to several stakeholders).
