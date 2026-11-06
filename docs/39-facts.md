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
| hold | none | on_hold, released (required) |

These encode the CRO's requirements. Contact info can be bounced or invalid.
A commitment is sent or drafted. An open question says whose move it is.
A role says its slot, so two decision owners show as a conflict.

**Partner-hold rule** (confirmed in writing by the CRO on PR #75,
6.11.2026). A `hold` fact records only the hold status, with
`source_kind = antti`. Any other source on a hold is refused. Nothing learned
in the partner's meetings behind a hold is entered as a fact; that part is
convention. The source
check guards the hold row, and any `source_kind` outside `FACT_SOURCES` is
refused. (To confirm with the CRO.)

## Releasing a hold, and failing closed (CRO additions, 6.11.2026)

- **A release is a hold fact** with `state = released` and
  `source_kind = antti`, which supersedes that account's `on_hold` fact
  (`supersede_fact(on_hold, released)`). The source rule is the same as for
  the hold, so a release from any other source is refused.
- **One account at a time.** `add_fact` takes one company and
  `supersede_fact` one pair of facts. No tool takes a list, a group or a
  segment, so there is no way to release a group.
- **Fail closed.** One active `on_hold` fact (source `antti`, no release)
  shows plain `HOLD`. The briefing also shows `HOLD` whenever the hold status
  is unclear, as `HOLD (unclear: <reason>)`:
  - two or more active hold facts (a conflict);
  - an active `released` fact that supersedes no `on_hold` fact of the same
    account;
  - any hold fact whose `source_kind` isn't `antti` (one that reached the
    table some other way, such as a direct load). The loader refuses it too
    (rule 3).

  Each unclear case lists the facts behind it, and the briefing never shows
  the account as released. "Unclear" is reserved for these anomalies (CRO).

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
- **conflicts**: two or more active `decision_owner` roles, or two or more
  active holds, with both sources shown. Picking one is the reader's job,
  never the code's. Two champions or two sponsors are normal on a real
  account, so they are listed under roles and **not** flagged: a conflict
  list that fires on them would teach people to ignore it (CPO review).

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

## Built (6.11.2026)

`schema.FACTS` with the per-kind vocabulary (`FACT_SLOTS`, `FACT_STATES`,
`HOLD_SOURCE`); `loaders.parse_fact_row` / `load_facts` (also in `load_all`,
`validate`, `export-all`, and the `load-facts` CLI); `log.add_fact` /
`log.supersede_fact`; `facts.list_facts` / `facts.group`; `briefing` gains
`hold` (first key) and `facts`; MCP `add_fact`, `supersede_fact`,
`list_facts`; API `GET /api/facts`, `POST /api/facts`,
`POST /api/facts/supersede`. Book: `book/test_facts.py`.

Two notes on how it was built:
- **The seed replica is generated, not hand-written.**
  `scripts/generate_seed.py` `make_facts` binds the replica to the seed
  account with the most people, and the hold to the first account with
  people and no deal. It draws no randomness, so every other seed file is
  unchanged, and a roster change moves the facts with it. The book reads
  the accounts and fact ids from `data/seed/facts.csv`.
- **Superseded hold rows still count** toward "a hold fact with another
  source". Failing closed means a foreign-source hold anywhere in the
  account's history shows `HOLD (unclear: ...)` until it is dealt with.
