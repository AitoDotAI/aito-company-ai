# Aito schema

Field lists below are the contract for seed data; when the real dataset
carries extra columns, preserve them as additional fields rather than
dropping them (CLAUDE.md rule 3: surprises are information).

## Evolving the schema (migrations)

`company-ai create-schema` brings a live instance up to the code's schema
**non-destructively**, using Aito's per-table and per-column schema API
(`PUT /api/v1/schema/{table}` and `PUT /api/v1/schema/{table}/{column}`):

- a **new table** → created;
- a **new column** on an existing table → added in place (no drop, no
  reload), via `PUT …/schema/{table}/{column}`;
- a column the live table has but the code doesn't → **reported, left in
  place** (never dropped).

It is idempotent — safe to run repeatedly; on an up-to-date instance it
reports "schema already up to date". Run it after pulling a change that adds
a table or column, e.g. `./do <cmd>` paths run it as part of seeding, or
directly: `COMPANY_AI_ENV=.env.aito uv run company-ai create-schema`.

**Backfill caveat.** Adding a column does not populate it on existing rows —
they read null until (re)loaded. For a column whose value is *derived at
load* (`won`, `slipped`, `days_since_prev_touch`, the funnel-stage booleans,
…), reload that table (`load-<table>`) to compute it for existing rows; for a
plain new field the values arrive on the next normal load. So: **new table →
`create-schema`; new derived column → `create-schema` then `load-<table>`.**

## contacts

One row per person. (Loaded from **`rolodex.csv`** — the file is named for
the rolodex, the table is `contacts`.)

| field | type | notes |
|---|---|---|
| contact_id | string | stable key |
| name | string | |
| company | string | |
| role | string | |
| phone_present | boolean | callability flag; the number itself stays in the private dataset and is surfaced by the loaders at runtime, never stored in seed |
| email_present | boolean | |
| segment | string | accounting, erp, ecommerce, analytics, consultancy, other |
| tier | string | A, B, C |
| ai_lifecycle | string | none, announced, shipped, operating |
| source | string | warm, trigger, cold, referral |
| country | string | |
| notes_tags | string[] | free tags |
| created | string (ISO date) | |

## touches

One row per contact attempt or event. This is the learning substrate.

| field | type | notes |
|---|---|---|
| touch_id | string | |
| contact_id | string | -> contacts |
| ts | string (ISO datetime) | |
| weekday | string | mon..sun, denormalized for inference |
| window | string | 0800, 1215, 1600, other |
| channel | string | call, email, linkedin, meeting |
| outcome | string | no_answer, callback_requested, conversation, meeting_booked, declined, bounced, reply, no_reply |
| days_since_prev_touch | string | derived at load/log time, never in CSV: bucketed recency (first, 0-2, 3-7, 8-21, 22+) at the moment of the touch; this is query 1's days_since_last_touch feature |
| next_action | string? | |
| next_action_due | string (ISO date)? | drives the 72h follow-up rule |
| notes | string? | |

## decisions

What the agent recommended, what the human did, what happened. Simplified
from an earlier prototype's decision-record design; the companion
pattern-extraction table was deliberately not ported because `_predict`
over this table replaces it.

| field | type | notes |
|---|---|---|
| decision_id | string | |
| ts | string (ISO datetime) | |
| decision_type | string | call_priority, opener_choice, followup_timing |
| context | object | window, weekday, segment, tier, ai_lifecycle |
| chosen | string | what the agent recommended |
| agent_confidence | number | the $p shown in the brief |
| human_action | string | accepted, overridden, ignored |
| human_alternative | string? | what the human did instead |
| outcome_after | string? | filled when the eventual outcome is known |

The `contacts` master also carries four derived funnel-stage booleans —
`ever_touched`, `ever_reached`, `ever_conversation`, `ever_meeting` —
stamped from touch history at load time (monotone; a load-time snapshot).
They feed the sales funnel; see `docs/09-funnels.md`.

## sessions

The website / acquisition funnel. One row per visitor session. Stage
booleans are monotone: `converted_paid` ⟹ `started_trial` ⟹ `signed_up`.
This is the inbound counterpart to `touches`; `source` and `campaign` are
the marketing dimensions. Full treatment in `docs/09-funnels.md`.

| field | type | notes |
|---|---|---|
| session_id | string | |
| ts | string (ISO date) | |
| source | string | organic, paid_search, social, referral, direct |
| campaign | string? | campaign name, when attributable |
| landing_page | string | /, /pricing, /docs, /blog, /demo |
| country | string | |
| device | string | desktop, mobile, tablet |
| signed_up | boolean | reached the signup stage |
| started_trial | boolean | reached the trial stage |
| converted_paid | boolean | reached the paid stage |

## posts

The distribution / messaging-formula log. One row per shipped post, the
feature vector and outcome — **no free-text title** (titles can carry
customer names). The scorer predicts `won` from the features. Full
treatment in `docs/10-messaging-formula.md`.

| field | type | notes |
|---|---|---|
| post_id | string | |
| channel | string | linkedin, hackernews, reddit, blog |
| posted_at | string (ISO date) | |
| weekday | string | derived from posted_at |
| tone | string | narrate, announce, explainer, builder |
| ai_made | string | manual, ai-assisted, ai |
| format | string | text, link, demo-link, thread, show-hn |
| link_placement | string | comment, body, n_a |
| lane | string | warm, cold |
| topic | string | content category (no PII) |
| length_chars | int | |
| length_bucket | string | derived: short, medium, long |
| reach_or_views | int | per-channel outcome: LinkedIn reach / HN views |
| upvotes | int | logged, **never** the target |
| trials | int | PLG attribution for cold drops |
| outcome | string | flop, modest, win |
| won | boolean | derived: `outcome == win`; the scorer's target |

## todos

The unified action source (architecture spec rev 3 §2.9). One row per
action; the Now view and the action blocks read it through three lenses.
Full treatment in `docs/12-todos-and-now.md`.

| field | type | notes |
|---|---|---|
| todo_id | string | |
| area | string | sales, distribution, operations, rnd |
| title | string | synthetic in seed (no PII) |
| detail | text? | |
| status | string | ready, draft, prog, blocked, done, monitor, on_track |
| priority | int | 1 = highest |
| due_date | string? | ISO date; required for sales/distribution, absent for operations/rnd |
| window | string? | e.g. fri_1430; paired with due_date |
| linked_id | string? | a contact_id, deal_id, or asset id |
| linked_type | string? | contact, deal, asset, instance, workstream |
| prep_status | string | prep_needed, ready, in_progress, blocked, n_a |

## deals

The sales pipeline (architecture spec §2.1). One row per opportunity. Open
deals are the current pipeline; closed deals are the close-likelihood
training substrate. Full treatment in `docs/13-deals.md`.

| field | type | notes |
|---|---|---|
| deal_id | string | |
| company | string | synthetic in seed (no PII) |
| segment | string | the offer segment (mirrors contacts.segment) |
| stage | string | lead, qualified, demo, pilot, negotiation, closed_won, closed_lost, parked |
| value_eur | int | |
| probability | int | 0–100, the operator's own estimate |
| champion_present | boolean | |
| blocker | string | none, consultant_lock, timing_mismatch, demo_readiness, budget, parked_intent, no_champion |
| last_touch_date | string (ISO date) | drives the stalled flag |
| created | string (ISO date) | |
| won | boolean? | derived from stage: closed_won → true, closed_lost → false, open → null; the predictor target |
