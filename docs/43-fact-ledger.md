# 43 — One fact ledger: structured, multi-source facts, listed (spec for review)

Status: **spec, approved with fixes by the CPO (8.11.2026); slice 1 approved
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
contacts, tooling). §4's conflict check reads it. **Prices are keyed by
unit.** One account can pay several price lines: a per-shop monthly fee,
and a licence plus a day rate. So `price` and `price_offered` are `one`
per (company, slot, unit), not per account. Two `EUR/month` prices
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

- `list_facts(company=, kind=, slot=, source_id=, status=)`: the ledger read.
- `add_fact_source(fact_id, source_kind, source_id)`.
- `confirm_fact(fact_id)`: a person's yes (remote: the operator's token only).
- `add_fact` as today, plus `value` and `unit`, and the twin lookup (§2).

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
   1 → 2 → 3 → 4, and slice 4 waits for decision 1.

## Build order (each slice fail-first, on the synthetic seed)

1. **The list views, no schema change.** The ledger read over today's
   columns, the Facts list in the Knowledge graph view, and "Facts from
   this note". Also the change-log `updated` row for document edits.
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
- **The two views.** Booktests print the ledger request, the response and
  the rendered list. The frontend tests cover both views.

## Not in this slice

- **Extraction in the app.** Extraction stays in the Claude session (rule
  1, docs/42).
- **Automatic supersede.** Facts aren't superseded on a source change;
  the change only flags them for review.
- **Contact edits.** Facts on contacts' own fields wait until contact
  edits reach the change log.
