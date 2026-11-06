# 39 — Account facts (spec for slice 2 of td-20261103224048158692)

Status: **spec, for review.** It implements part (a) of the design Antti
approved on 3.11.2026 (the ticket text is the source), and the facts half of
(b), `briefing`. Recall (c), the thin-doc flag (d), the marks table and mail
ingest are later slices, and not built here. Creating the `facts` table on
internal is a schema write, and waits for Antti's yes.

## Why

The account's current state was buried in a long newest-first rolodex cell,
so a call-prep answer named the wrong person as decision owner (3.11). A fact
is one short, sourced statement about an account. It stays true until
another fact supersedes it.

## The `facts` collection

The documents pattern (docs/25): one row per fact, linked to its company.

| column | type | notes |
| --- | --- | --- |
| `fact_id` | String | `fa-<stamp>` |
| `company` | String | display name, kept |
| `company_id` | String, link `companies.company_id` | the account (`add_company` first, so it never dangles) |
| `stakeholder_id` | String, nullable, link `contacts.contact_id` | the person, when the fact is about one |
| `kind` | String | `FACT_KINDS`: role, commitment, decision, open_question, contact_info, hold |
| `slot` | String, nullable | per kind, below |
| `state` | String, nullable | per kind, below |
| `statement` | Text (english) | short, as written: never generated |
| `due` | String, nullable | a commitment's date |
| `source_kind` | String | `FACT_SOURCES`: mail, doc, call, touch, antti |
| `source_id` | String | the mail, document, touch or note id |
| `valid_from` | String | the date the fact became true (YYYY-MM-DD) |
| `superseded_by` | String, nullable | the `fact_id` that replaced it; null while active |
| `author` | String | who recorded it (a slug: `cro`, `antti`, …) |
| `created_at` | String | write time |

The per-kind vocabulary. A value outside it, or a `slot` or `state` on a kind
that has none, is refused with the row (rule 3):

| kind | `slot` | `state` |
| --- | --- | --- |
| role | champion, decision_owner, sponsor, other (required) | none |
| commitment | ours, theirs (required) | sent, drafted (required) |
| open_question | ours, theirs: **whose move** (required) | none |
| contact_info | none | current, bounced, invalid (required) |
| decision | none | none |
| hold | none | none |

These encode the CRO's requirements. Contact info can be bounced or invalid.
A commitment is sent or drafted. An open question says whose move it is.
A role says its slot, so two decision owners show as a conflict.

**Partner-hold rule.** A `hold` fact records only the hold status, with
`source_kind = antti`. Any other source on a hold is refused. Nothing learned
in the partner's meetings behind a hold is entered as a fact; that part is
convention. The source
check guards the hold row, and any `source_kind` outside `FACT_SOURCES` is
refused. (To confirm with the CRO.)

## Writes, tools and the change log

- `add_fact(company, kind, statement, source_kind, source_id, valid_from, author, slot?, state?, due?, stakeholder_id?)`:
  validated as above, then inserted on the retry-safe path (a retried call
  inside the retry window returns the earlier row, as `add_document` does).
  It writes a change-log row (`fact`, `created`).
- `supersede_fact(old_id, new_id)`: both must exist, be on the same company
  and the same kind, and `old` must still be active. It sets
  `old.superseded_by = new` with `_write_row` (one row, read back), and
  writes a change-log row (`fact`, `superseded`). It is never applied
  automatically.
- `list_facts(company, active_only=True)`: the facts, newest `valid_from`
  first.

All three are MCP tools and API routes. `add_fact` and `supersede_fact` are
safe writes on the remote surface, as `add_document` is.

## `briefing` with facts

`briefing(company)` (slice 1, #72) gains these groups. They come from
**active** facts only (`superseded_by` null), and each fact carries
`source {kind: fact, id, date: valid_from}` plus its own
`source_kind`/`source_id`:

- **hold**, first: a hold fact puts `HOLD` at the top of the briefing.
- **roles**, by slot: champion, decision owner, sponsor, other.
- **commitments**, ours and theirs, with `due` and `state`. A drafted one
  is listed as **drafted, not sent**, and never as communication.
- **decisions**, newest first. Each shows the fact it replaced: the fact
  whose `superseded_by` is this one.
- **open questions**, with whose move.
- **contact info**: current ones only. Bounced and invalid ones are listed
  apart as not current, never as an address to use.
- **conflicts**: two or more active `role` facts in the same slot (other
  than `other`), or two active holds, with both sources shown. Picking one
  is the reader's job, never the code's.

"Last touch" is already in slice 1 (stakeholders and touches). Nothing is
ranked or inferred: grouping by `kind`/`slot`, and sorting by date.

## Acceptance (T1, fail-first, synthetic)

A synthetic replica account goes in the seed (`data/seed/facts.csv`, loaded
by `load_facts`, no real names), and the book asserts that the briefing:

1. names the commercial lead as decision owner, sourced to the 26.10 split;
2. flags the 1.11 sponsor "decides what is sold" fact as a conflict in the
   decision-owner slot, with both sources;
3. shows the 2.11 decision mail went to the decision owner;
4. shows the older champion "buy versus publish, 9.10" fact as an open
   question, not as ownership.

Plus the CRO's requirements: a hold on top, a bounced address not current,
a drafted commitment marked not sent, and an account with facts but no deal.
`supersede_fact` takes a fact out of the briefing, and a refused value shows
the row. T1-live (against internal, once the CRO has seeded real facts) is a
`./do maintenance` check, after Antti's yes for the table.

## Not in slice 2

Recall (`search_items` and vectors, supersede candidates by `$nearest`), the
contexts/marks tables, the thin-doc flag, mail ingest, and T2 (the mail-recall test).
