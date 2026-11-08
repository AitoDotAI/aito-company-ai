# 43 — One fact ledger: structured, multi-source facts, listed (spec for review)

Status: **spec, for review.** Nothing here is built until the decisions
below are settled. It extends docs/39 (the `facts` collection), docs/41
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
in the same vocabulary file: `price` (value + unit), `contract_end`
(a date). Every new slot needs the CRO's word, as in docs/42.

**"Is a customer" is not written; it's derived.** A won deal already says
so. The ledger lists it as a derived fact, from the same rows the graph's
node facts use (`loaders.harvest`), with the deal as its source. A
hand-written `is customer` fact would drift from the deals. Rule 3 then
applies: a won deal and a fact saying "not a customer" is a conflict,
raised with both rows.

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
- **`add_fact` finds its twin.** When an active fact with the same
  company, kind, slot and value exists, `add_fact` writes nothing new. It
  returns that fact, and `add_fact_source` is the call to make. This is an
  exact lookup, not a similarity, so it stays out of rule 2's way.

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
- **review: source changed.** A source row has a change-log entry after
  the fact's `created_at`.
- **review: source missing.** A source is dangling (docs/41).
- **review: conflict.** Another active fact has the same conflict slot
  and a different value.

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
3. **"Is a customer" is derived from won deals, never written** (§1).
   *CPO / CRO.*
4. **The new slots** `price` and `contract_end`. *CRO.*
5. **The order of the build** (below). *CPO.*

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

- **Twin lookup.** `add_fact` on a twin writes no row and returns the
  existing fact. `add_fact_source` then lists two sources in the ledger.
- **Source changed.** Editing a source doc moves its facts to "review:
  source changed".
- **Derived customer status.** A won deal lists "is a customer" as a
  derived fact citing the deal id. A conflicting written fact raises,
  with both rows.
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
