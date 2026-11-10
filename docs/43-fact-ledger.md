# 43 — One fact ledger: structured, multi-source facts, listed (spec for review)

Status: **spec, approved with fixes by the CPO (8.11.2026); slice 1 built; slice 1b (§7, the CRO's account sheet) approved by Antti 10.11.2026
to build.** Slices 2–4 wait for the decisions below. It extends docs/39 (the `facts` collection), docs/41
(sources that resolve) and docs/42 (harvesting from notes).

## The ask (Antti, 8.11.2026)

Agents keep struggling with plain account truths: is this account a
customer, what does it pay, who signs. The ask:

- **Facts as subject–predicate–value**, each linked by id to the records
  that say so. "Nakatomi is a customer (sources: deal D-…, doc d-…)",
  "Nakatomi pays 990 € a month (source: doc d-…)".
- **Several sources per fact.** A second note that says the same thing
  corroborates the fact instead of duplicating it.
- **Agents may insert facts.** The CRO session, for one, should be able
  to write what it learns, not only propose it.
- **Extraction from documents**, with each note showing the facts
  taken from it.
- **One list** of every fact, whatever its source (contacts, companies,
  deals, notes, touches), to look items up by id and keep facts current.
  It sits in the Knowledge graph view as a **list, not a visualisation**.
  The graph stays for one account's unfold (docs/41).
- **Maintenance:** a fact whose source record changed, or that a newer
  fact contradicts, is visibly due for review.

## What exists (docs/39–42)

- **The collection.** `facts`: one statement per row. Each row has
  `company_id` and an optional `stakeholder_id`, linked. Its `kind` and
  `slot` come from a fixed vocabulary.
- **Sources.** Exactly one source per fact (`source_kind`, `source_id`),
  resolved at read time as linked, external or dangling.
- **Supersede.** A fact is replaced by a newer one through `supersede_fact`
  and is never deleted.
- **Harvesting.** `harvest_queue` gives the Claude session an account's
  notes. The session proposes facts, a person confirms, and `add_fact`
  writes them (docs/42).
- **Derived node facts.** The node facts a load derives (tier, open
  deals…) carry the rows they came from (`loaders.harvest`, docs/41).
- **MCP.** `add_fact`, `list_facts` and `supersede_fact` are MCP tools,
  and the remote surface allows them. **Not deployed until main is.**

## 1. The shape: predicate and value, on the existing vocabulary

No parallel vocabulary. The **predicate is the existing `kind` + `slot`**
(`attribute/billing_model`, `role/signer`…). Two new nullable columns
carry a value that can be compared:

| column | type | example |
|---|---|---|
| `value` | String, nullable | `990`, `monthly`, `2027-03-31` |
| `unit`  | String, nullable | `EUR/month`, `date`, `seats` |

`statement` stays as the human sentence ("pays 990 € a month on the
annual plan"); `value` is what an agent looks up. New `attribute` slots,
in the same vocabulary file (the CRO's word, 8.11.2026):

- **`price`: agreed and paying only.**
- **`price_offered`: a price in a sent proposal.** Keeping the two apart
  stops the briefing stating a proposal as revenue.
- **`contract_end`: an ISO date.** (`notice_period`, a renewal trigger,
  comes later, not in this slice.)

**Units are a closed set**, written into the vocabulary file so agents
don't invent spellings: `EUR/month`, `EUR/year`, `EUR/day`, and per-unit
as a suffix (`EUR/month/shop`). Money values exclude VAT. `date` is for
`contract_end`.

**Cardinality.** Each slot gets a cardinality in the vocabulary file:
`one` (a contract end, a decision owner) or `many` (signers, billing
contacts, tooling). §4's conflict check reads it. **`price` and
`price_offered` are one per (company, unit), not one per account.** One
account can pay several price lines: a per-shop monthly fee, or a licence
plus a day rate. Two `EUR/month` prices
conflict; an `EUR/month` and an `EUR/day` don't.

**"Is a customer" is derived, never written** (decision 3, settled by the
CPO 8.11.2026). A hand-written "is a customer" fact is refused: it would
drift from the deals. The ledger lists customer status as a derived fact,
from the same rows the graph's node facts use (`loaders.harvest`), with its
sources. An account is a **customer** when either:

- **Direct.** It has a won deal with no later lost or churn event on that
  deal (`deal_events`, docs/34), and no active `contract_end` fact in the
  past. A won deal whose contract has ended makes a **former customer**.
- **Indirect.** It buys through a partner and has no deal of ours. That
  is one written fact, `relationship/customer_via`, whose `value` is the
  partner account's `company_id`. The derivation reads it and lists
  "indirect customer via <partner>" (one such account is a published
  case). The same shape covers a partner's own end customers.

The new `relationship` kind has one slot, `customer_via` (cardinality
`many`).

**No negative from absence** (the CRO's standing rule). An account with
no won deal and no `customer_via` fact is listed as **"no won deal on
record"**, never "not a customer". Older customers may predate the deals
table, so their won deals are backfilled before the derived status is
shown on internal.

## 2. Several sources: a `fact_sources` collection

| column | type | |
|---|---|---|
| `fact_source_id` | String | |
| `fact_id` | String, link → `facts.fact_id` | |
| `source_kind`, `source_id` | String | as on `facts` today |
| `added_by`, `added_at` | String | who corroborated it, and when |

- `facts.source_kind`/`source_id` stays as the **first** source, so every
  reader today keeps working.
- A new tool, `add_fact_source(fact_id, source_kind, source_id)`, adds
  another. It's validated like `add_fact`'s source: a doc or touch must
  resolve, or it warns.
- **`add_fact` finds its twin**, but only when `value` is set. When an
  active fact with the same company, kind, slot and normalised value
  exists, `add_fact` writes nothing new. It returns that fact, and
  `add_fact_source` is the call to make. **A null value never twins.**
  Most facts today have no value, and a twin rule over (company, kind,
  slot) alone would swallow a different statement in the same slot. This
  is an exact lookup, not a similarity, so it stays out of rule 2's way.
- **Values are normalised by unit before they're compared or stored.** A
  money unit's value is a decimal with two places ("990" → "990.00"). A
  `date` value is YYYY-MM-DD. A value that doesn't parse for its unit
  raises, with the row (rule 3). The statement keeps the words as written.

## 3. Agents writing facts

docs/42 decided that only confirmed facts are written. The ask widens
that, so it is **decision 1**. The proposal:

- **Who may write.** An agent may call `add_fact` and `add_fact_source`,
  with `author` set to its id (`cro`, `cpo`…).
- **The new column.** `confirmed_by` (String, nullable): null until a
  person confirms it with `confirm_fact(fact_id)`.
- **Where an unconfirmed fact shows.** The briefing, the ledger and the
  unfold show it marked "unconfirmed (cro)". The briefing's answer line
  never states it as settled.
- **Unchanged.** Holds and releases stay Antti's only (`HOLD_SOURCE`).

## 4. Due for review: computed at read, never stored

A fact's `status` in the ledger is one of:

- **active**;
- **unconfirmed** (§3);
- **superseded** (it has `superseded_by`);
- **review: source changed.** A source row has a change-log `updated`
  entry after **that source was attached**: `fact_sources.added_at`, or
  the fact's `created_at` for its first source. It's not the fact's own
  date, because then fixing a typo in a note would flag every fact
  harvested from it earlier, all at once. An edit made in the same harvest
  pass, before the fact was attached, doesn't count.
- **review: source missing.** A source is dangling (docs/41).
- **review: conflict.** Another active fact has the same **single-valued**
  slot (cardinality `one`, §1) and a different normalised value.
  Multi-valued slots, such as two signers, never conflict.

**Prerequisite, its own small fix.** Editing a document writes no
change-log row today: `update_document` records nothing, and only
`created` is logged. The "source changed" check needs that row, so
documents (and contacts, when edits arrive) must log `updated` first.

## 5. The views

**Knowledge graph → Facts.** This is the list, beside the existing
graph. Its columns:

- the subject, a link to the account or contact;
- the predicate, as kind/slot;
- the value with its unit;
- the statement;
- the sources, each a link by id that opens the record;
- the status from §4;
- the author.

Filters: account, predicate, source kind, status. Search by any record
id lists the facts that cite it, which is the "look items up by id" ask.

**A document → "Facts from this note".** It lists the facts whose first
source, or any added source, is this doc, each with its status. This is
`list_facts(source_id=)`, a lookup.

Both are read-only views over one new read, `facts.ledger(filters)`:
exact matches, no ranking. Writes stay in the tools (§2, §3).

## 6. Tools (MCP, the remote surface too)

- `fact_ledger(company=, kind=, slot=, source_id=, status=)`: the ledger read
  (MCP; `GET /api/facts/ledger`). `list_facts` stays as it is.
- `add_fact_source(fact_id, source_kind, source_id)`.
- `confirm_fact(fact_id)`: a person's yes (remote: the operator's token only).
- `add_fact` as today, plus `value` and `unit`, and the twin lookup (§2).

## 7. What the CRO needs first: one account's sheet (10.11.2026)

Antti asked the CRO session which view would serve it, from what it had
actually done (9–10.11.2026), not from this spec. Its answer reorders the
build more than it changes the design.

**What it found.** Almost none of its account knowledge came from Company
AI. Each account picture took 4–6 calls plus file greps over the repo's
notes, a CSV and mail, and its confident mistakes came from that:

- **Touches it couldn't see.** Calls and texts logged nowhere made it
  miscount an account's unanswered streak twice. That count decides when
  to stop chasing.
- **State without a date or source.** It stated two things as current
  that weren't.
- **No line between "no record" and "not where I looked".** The ledger
  already holds this rule ("no won deal on record", §1), but the CRO can
  only use it if the sheet is the one place it looks.

**The questions it needs answered, in its order:**

1. the relationship: customer, prospect, implemented by a partner,
   indirect through a channel, or held;
2. the last touch, its channel, and how many in a row went unanswered;
3. who has to act and who is only the champion; several roles can each
   veto passively;
4. what was promised, by whom, and whether it's done;
5. which terms and prices have been said, and which must not be;
6. agreement status: NDA, DPA, who has yet to sign;
7. the next booked step and its date.

It starts from an account, not from a record id, so lookup by id matters
less to it.

### 7a. The account sheet (built next, no schema change)

The company pane gets a **Facts** section: one account's facts grouped
by kind and slot, which is `facts.group` (the briefing's grouping, docs/39)
read through the ledger, so every row carries its status (§4). It shows:

- **Each fact** with its statement, `valid_from`, source by id, author and
  status, newest first within its slot.
- **Superseded facts collapsed, not hidden**: "2 earlier" opens them.
- **"Touched since"**: a fact older than the account's latest touch is
  marked "touched since <date>", that touch's date. This is a pointer,
  not a review status: most facts outlive many touches, so it never moves
  a fact to review and is never labelled "stale".
- **The touch line at the top**: the latest touch with its date, channel
  and direction, and the unanswered streak (7c).
- **Derived customer status** (§1): direct only in this slice ("customer"
  from a won deal not since lost, citing the deal id; otherwise "no won
  deal on record"). Indirect waits for `relationship/customer_via`, so
  the line always carries the qualifier **"direct deals only; indirect
  relationships are not shown yet"**: without it, an account we serve
  through a partner would read as not a customer.

The same read is the MCP tool `account_sheet(company)`, so the CRO gets
one call instead of 4–6. `briefing` stays as it is.

### 7b. Two lists across accounts (built next, no schema change)

- **We owe it, and it's overdue.** Active `commitment/ours` facts not yet
  `sent` (a sent one is delivered) whose `due` is before today **in Europe/Helsinki** (`clock.today()` taken in
  that zone, or the configured as-of date), oldest first. At 01:00 Helsinki
  a commitment due that day isn't yet overdue, whatever UTC says.
- **Stop chasing.** Accounts whose unanswered streak (7c) is 3 or more,
  longest first, for the Sunday board review.

Both are exact reads and counts, no ranking (rule 2). They sit beside the
Facts list in the Knowledge graph view and are MCP tools
(`overdue_commitments`, `unanswered_accounts(min_streak=3)`).

### 7c. The unanswered streak

Over the account's touches, newest first, across all its contacts:
count the `out` touches until the first touch that is either `in`, or
has outcome `conversation`, `meeting_booked`, `reply`, `callback_requested`
or `declined`, **whatever its recorded direction**. A meeting we hosted may
be logged `out`; it is still an answer. A decline is an answer too: it ends
the chase by another route.

- **An auto-reply, out-of-office or bounce is not an answer.** It is
  recorded as the out touch's outcome (`bounced`, `no_reply`), never as an
  `in` touch, so it can't reset the streak. `log_touch` says so in its
  description.

- **A touch with no recorded direction** (docs/34: null means not
  recorded) stops the count, and the sheet says "streak unknown before
  <date>". It isn't counted as out, and isn't skipped.
- **Calls and texts count only once they're logged.** `log_touch`
  already takes `call` and `sms` (`TOUCH_CHANNELS`). Logging them is the
  operator's and the CRO's habit to fix, not code; the sheet shows the
  channel so a gap is visible.

### 7d. Later, and whose call

- **Terms said and "never say".** A new kind `terms`, slots `said` and
  `never_say`, and a kind `agreement` with slots `nda`, `dpa` and states
  `pending_signature`, `signed`. These are vocabulary, not schema. Both are
  sensitive, so they are **written only on Antti's word**, like holds
  (`HOLD_SOURCE`), and the remote surface never shows `never_say` facts.
  *Antti.*
- **Harvest at write time.** When the session writes a `call;outcome` or
  `call;prep` note, it proposes facts from that note in the same pass
  (docs/42: in the session, not the app). One account at a time, before a
  meeting, rather than a backlog.
- **What may be batch-confirmed** (with decision 1): touch and next-step
  facts taken from a primary source (sent mail, the calendar). The
  relationship, terms and holds are never batch-confirmed, and an agent's
  inference never confirms them.
- **"Asserted by"** is §3's `confirmed_by` plus `author`: a person, a
  primary source, or an agent's inference.

## Decisions for review

1. **Agents write unconfirmed facts** (§3), against docs/42's
   confirm-first rule. *Antti.*
2. **The schema additions**: `value`, `unit` and `confirmed_by` on
   `facts`; the new `fact_sources` collection. These are internal schema
   changes, made with a backup first. *Antti.*
3. **"Is a customer" is derived, never written** (§1). *Settled by the
   CPO, 8.11.2026:* direct (a won deal not since lost, churned or ended)
   or indirect (one `relationship/indirect_customer` fact).
4. **The new vocabulary**: slots `price`, `price_offered` and
   `contract_end`, the unit set, the `relationship/customer_via` kind and
   slot, and each slot's cardinality. *Settled by the CRO, 8.11.2026.*
5. **The order of the build** (below). *Settled by the CPO, 8.11.2026:*
   1 → 2 → 3 → 4, and slice 4 waits for decision 1. *Amended 10.11.2026:*
   slice 1b (§7) goes before 2.
6. **The terms and agreement vocabulary** (§7d), written on Antti's word
   only. *Antti.*

## Build order (each slice fail-first, on the synthetic seed)

1. **The list views, no schema change.** The ledger read over today's
   columns, the Facts list in the Knowledge graph view, and "Facts from
   this note". Also the change-log `updated` row for document edits.
   *Built, 8.11.2026.*
   - **1b. The account sheet and the two lists (§7a–7c), no schema
     change.** Antti approved 10.11.2026, after the CRO's answer. It goes
     before slice 2.
2. **Several sources.** `fact_sources`, `add_fact_source` and the twin
   lookup.
3. **Structured values.** `value`, `unit` and the new slots.
4. **Agent writes.** `confirmed_by` and `confirm_fact`, plus the
   unconfirmed marking in the briefing.

## Acceptance (fail-first, synthetic seed)

- **Twin lookup.** `add_fact` on a twin with a value writes no row and
  returns the existing fact; "990" twins "990.00". `add_fact_source` then
  lists two sources in the ledger. Two null-valued facts in one slot stay
  two facts.
- **Source changed.** Editing a source doc after a fact was attached
  moves that fact to "review: source changed". A fact attached after the
  edit stays active.
- **Conflict.** Two `EUR/month` prices on one account conflict. An
  `EUR/month` price and an `EUR/day` price don't, a `price_offered`
  never conflicts with a `price`, and two signers don't conflict.
- **Units.** A unit outside the closed set (`€/kk`) raises, with the row.
- **Derived customer status.** A won deal lists "customer", citing the
  deal id. A later churn, or a past `contract_end`, lists "former
  customer". A `relationship/customer_via` fact lists "indirect customer via
  <partner>". An account with neither lists "no won deal on record". A
  written "is a customer" fact raises, with the row.
- **Lookup by id.** The ledger, filtered by a doc id, equals the
  document's "Facts from this note" list.
- **Unconfirmed.** An agent-written fact shows "unconfirmed" until
  `confirm_fact`, and the briefing doesn't state it as settled.
- **The account sheet.** On the seed, one account's sheet groups its
  facts by slot with a superseded fact collapsed under its successor, the
  derived status cites the won deal, and a fact older than the latest
  touch carries exactly "touched since <date>" while its status stays
  active (the test pins the wording, so it can't become a staleness
  signal). An account with no won deal shows "no won deal on record" with
  the qualifier "direct deals only; indirect relationships are not shown
  yet".
- **The streak.** Three `out` touches after an `in` one count 3; an `out`
  with outcome `declined` ends the count, and so does an `out` meeting
  with outcome `meeting_booked` or `conversation`; a touch with no
  direction stops it and the sheet says so. A commitment due yesterday
  (Helsinki) is on the overdue list, and one due today is not.
- **The two views.** Booktests print the ledger request, the response and
  the rendered list. The frontend tests cover both views.

## Not in this slice

- **Extraction in the app.** Extraction stays in the Claude session (rule
  1, docs/42).
- **Automatic supersede.** Facts aren't superseded on a source change;
  the change only flags them for review.
- **Contact edits.** Facts on contacts' own fields wait until contact
  edits reach the change log.

## Built: slice 1 (8.11.2026, td-20261108214053518773)

- **The ledger read.** `facts.ledger(company, kind, slot, source_id,
  status)`, exact filters, served as `GET /api/facts/ledger` and the MCP
  tool `fact_ledger`. Statuses so far: active, superseded, review: source
  missing, review: source changed. Conflict waits for slice 3's
  cardinality, unconfirmed for slice 4.
- **Source changed.** Measured against the fact's `created_at`, which is
  when its only source was attached. Slice 2 moves it to
  `fact_sources.added_at`.
- **Read limits.** One ledger read takes at most 10,000 facts
  (`facts.READ_LIMIT`), and the change-log lookup for their cited
  documents at most 10,000 `updated` rows. Past either it raises, rather
  than answering from a truncated page (rule 3); a filter narrows it.
- **Document edits are logged.** `update_document` writes a change-log
  `updated` row naming the changed fields.
- **The views.** The Knowledge graph view opens with the Facts list.
  Clicking a source id narrows it to the facts citing that record, and
  the record id filter does the same for any id. The document pane lists
  "Facts from this note".
- **Tests.** `book/test_fact_ledger.py` (5 cases) and
  `frontend/src/factledger.test.jsx` (6).

## Built: derived customer status (11.11.2026, td-20261111001541681626)

- **`facts.ledger` lists customer status** as read-only rows (kind and status
  `derived`, slot `customer_status`). There's one per account with a
  `closed_won` deal, citing each won deal in `sources`. Filtered to an account
  with none, it reads "No won deal on record". Every row carries "direct deals
  only; indirect relationships are not shown yet". Nothing is written: the rows
  are read from the deals on each call. A deal id finds the row that cites it.
- **Dated by the earliest win**: the deal's move into `closed_won` in
  `deal_events`, else the won deal's `created`. `valid_from_field` names which.
  A later touch on the deal doesn't move it (CPO review).
- **Asked by Antti** because the live Facts list is empty until a harvest runs.
- **The account sheet** keeps its own status line and leaves the derived row out
  of its slots.
- **Tests.** `test_customer_status_is_listed_as_a_derived_row` and a frontend case.

## Built: slice 1b (10.11.2026, td-20261110230516558720)

- **`sheet.account_sheet(company)`** (MCP `account_sheet`, `GET
  /api/facts/sheet`): the ledger's rows for one account grouped by kind and
  slot, superseded ones under `earlier`, "touched since <date>" as a
  pointer, the latest touch and the streak, and direct customer status with
  its qualifier. The company page shows it as **Facts**.
- **`sheet.overdue_commitments()`** (MCP, `GET /api/facts/overdue`) and
  **`sheet.unanswered_accounts(min_streak=3)`** (MCP, `GET
  /api/facts/unanswered`). Both are in the Knowledge graph view under the
  Facts list. A touch belongs to its company_id, else to its contact's
  company, the same as on the sheet. Touches with neither are counted, not
  dropped.
- **`log_touch`'s description** says that calls and texts must be logged
  too, and that an auto-reply or bounce is the out touch's outcome.
- **On real data (10.11.2026):** 47 of 314 touches record no direction, so
  some accounts' streaks read "unknown before <date>".
- **Tests.** `book/test_account_sheet.py` (5 cases; the streak test goes
  red with `meeting_booked` taken out of the answers) and
  `frontend/src/accountsheet.test.jsx` (8).
