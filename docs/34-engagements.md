# 34 — Engagements: the sales funnel's raw rows

A row in `touches` is one **engagement**: an email, call, SMS, LinkedIn touch
or meeting, outbound or inbound, linked to its contact, its company and — when
there is one — its deal. This is the data the sales predictions learn from,
so this page is about getting enough of it in, with the details that matter.

Why it exists (12.10.2026): the live instance had 61 contacts against a
120-row rolodex, and every open deal read as stalled, because engagements were
not being logged. The predictions were starved, not wrong.

## The row

The original columns are unchanged (`touch_id`, `contact_id`, `ts`, `weekday`,
`window`, `channel`, `outcome`, `next_action`, `next_action_due`, `notes`).
All new columns are nullable; null means *not recorded*, never *none*.
Categoricals are `String` (one exact value, one feature), not `Text`.

| column | values | only on |
|---|---|---|
| `deal_id` | link → `deals.deal_id` | |
| `direction` | out, in | |
| `answered_by` | person, voicemail, switchboard, gatekeeper, none | channel = call |
| `linkedin_kind` | connect, dm, comment, post_engagement | channel = linkedin |
| `meeting_kind` | first, follow_up, demo, technical, pilot, negotiation | channel = meeting |
| `reply_sentiment` | positive, neutral, polite_no, negative | direction = in, or outcome = reply |
| `source` | warm, trigger, cold, referral (`SOURCES`) | |
| `hook` | the opener's angle, ≤ 120 characters | |
| `template` | id of the copy pattern | |
| `language` | fi, en, sv (`LANGUAGES`, deployment vocabulary) | |
| `gmail_thread_id` | | channel = email |
| `calendar_event_id` | | channel = meeting |

`channel` gains `sms`.

**Derived, never written by a caller:** `hour` (from `ts`), `company_id` (the
contact's), and `step` — the 1-based position of an outbound engagement in its
contact's sequence. Inbound rows have no step. A touch with no `direction`
(the older hand log) counts as outbound. `window`, when not given, is the call
window `ts` falls in: a window covers the two clock hours from its start hour
(`schema.window_for`), the convention the hand-logged rows already follow.

`step`, the recency bucket and the company are properties of the contact's
*whole* history, so `engagements.resequence` recomputes them for every touch of
every contact a write affects — a backfill arrives out of order, and one older
row renumbers the rows after it. The same pass:

- re-derives the contact's **funnel flags** (`ever_touched` … `ever_meeting`).
  These used to be stamped only at load time, so live-logged touches never
  moved the sales funnel;
- moves a linked deal's **`last_touch_date`** forward to its latest
  engagement, so a deal being worked does not read as stalled.

## Deals

- `source` (`SOURCES`), `first_meeting_date`, and `lost_reason`.
- **One reason vocabulary.** `blocker` (what stops an open deal now) and
  `lost_reason` (why a closed one was lost, `closed_lost` only) share
  `DEAL_BLOCKERS`, so stalls and losses count in one set. It gained
  `no_decider`, `group_owned`, `build_in_house`, `no_burning_need`, `capacity`,
  `competitor`, `gone_silent`; the sales lane's "timing" and "price" are the
  existing `timing_mismatch` and `budget`.
- **`deal_events`** — the path through the stages: one row each time a deal's
  stage or blocker changes (`deal_id`, `date`, `stage`, `prev_stage`,
  `blocker`, `segment`), written by `add_deal` and `log_deal_update`. App
  state like the changelog: no CSV, starts empty.
- `log_deal_update` now updates the row in place (`_modify`, read
  back). It used to drop and rewrite the whole table, which was safe only
  while nothing linked to deals.

## Writing engagements

- **One at a time:** MCP `log_touch` (and `company-ai log`) takes every column
  above as an optional argument; `ts` defaults to now, `window` to the window
  of `ts`. A detail on the wrong channel is refused.
- **In bulk:** `./do import-engagements <csv> [config] [--apply]`. The CSV
  header, in this order:

  ```
  touch_id,contact_id,deal_id,ts,channel,direction,outcome,answered_by,linkedin_kind,meeting_kind,reply_sentiment,source,hook,template,language,gmail_thread_id,calendar_event_id,next_action,next_action_due,notes
  ```

  - `touch_id` is the idempotency key: a stable id from the source
    (`gm-<gmail message id>`, `cal-<event id>`, …). Re-importing a row
    updates it in place; it never duplicates it. A touch_id that already
    belongs to another contact is refused.
  - `ts` is local time with no offset; a row in UTC (`Z`, `+00:00`) is
    refused, since a shifted hour is exactly what the call timing learns from.
  - `contact_id` and `deal_id` must already exist.
  - Every row is checked first and every problem reported at once, by line.
    If any row is refused, nothing is written.
  - Without `--apply` it only plans: new / changed / unchanged, plus
    *possible duplicates* — a new row on the same contact, channel and day as
    an existing hand-logged touch. Those are imported anyway (two calls in a
    day are real) but listed so a person can check.
  - With `--apply` it takes a `tx` backup first, then inserts, updates and
    resequences.

  Mapping guidance for a backfill: an inbound reply is `direction=in,
  outcome=reply` plus a sentiment; a held meeting is `outcome=conversation`, a
  no-show `outcome=no_answer`; the mail that booked a meeting is the outbound
  row with `outcome=meeting_booked`; a sent mail with no answer is
  `outcome=no_reply`.

## The weekly KPIs

`engagements.weekly` — MCP `engagement_kpis`, `GET /api/engagements`,
`company-ai engagement-kpis`, and the *Engagements by week* block on the Sales
→ Analytics tab. Per ISO week: engagements, outbound by channel, inbound, new
contacts touched (outbound step 1), calls answered by a person (over the calls
that recorded `answered_by`), email replies in vs mails out, meetings booked
and held, meetings per 10 first touches; plus open deals by blocker and lost
deals by reason.

This is counting, like `saleskpi.py` — deterministic accounting, not
prediction (rule 2). A rate over nothing is `null`, shown as "—", never 0.

## What the data is for (next)

Once the rows exist, the questions are Aito queries over them, not new code:
`_predict answered_by` given weekday, hour and role (when to call whom);
`_predict outcome` given source, hook, segment and step (which message, which
step); `_relate` over `deal_events` blockers by stage (what kills deals, and
where). Those land as their own booktested queries, each against the seed
first (rule 4).
