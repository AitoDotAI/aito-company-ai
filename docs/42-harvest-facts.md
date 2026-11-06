# 42 — Harvesting account facts out of meeting notes (spec for td-20261106233617731095)

Status: **spec, for review.** It covers part 3 of td-20260926220007895967,
whose parts 1 and 2 are docs/41. **Nothing is built until the decisions below
are settled.**

## The ask

Today a fact gets written only when someone states it with `add_fact`. The
notes already carry many: the seed's account notes were written with them in.
- **Nakatomi's account plan:**
  - the COO is the technical champion;
  - procurement starts once they're convinced;
  - the budget cycle resets in Q1;
  - they bill on milestones, not seats.
- **Slate's discovery call:** they're mid-migration, so timing is the blocker,
  not fit.
- **Genco's account plan:** a legacy stack.

The ask is to get those into `facts`, sourced to the note (`source_kind: doc`),
so the briefing and the unfold (docs/41) show them with their "says who?".

## 1. Where the reading happens: the Claude session, not the app (rule 1)

Reading a note and stating its facts is model work. Rule 1 allows a model in
the app only in three fenced places, and none of them writes facts. A routine
(the third) may write only its document note and its tick. **So the reading
runs in the Claude session over MCP, the same way a human-confirmed
`add_fact` does today.** The app adds plumbing only:

- **`harvest_queue(company)`**, a read tool that is pure lookups:
  - the account's notes, newest first;
  - for each, the active facts that already cite it (`source_id` = its
    `doc_id`) and its body;
  - the account's other active facts, so the session doesn't restate them.

  It doesn't rank notes or guess at their facts (rule 2). A thin note
  (docs/40) is flagged as such.
- **A held account is not harvested** (CRO). When the account's `briefing`
  hold reads HOLD, including HOLD (unclear: …), `harvest_queue` returns the
  hold and no notes. A row can't show that a note came from a partner meeting,
  so skipping held accounts is the guard that can be enforced. It fails closed
  with the briefing's own hold reading (docs/39).
- **The session proposes, a person confirms, and then `add_fact` writes**, with
  `source_kind: doc` and the note's `doc_id`. `add_fact`'s
  `supersede_candidates` (docs/40) already shows what a new fact may replace;
  the session never supersedes on its own.
- **Not a routine.** A scheduled harvest would be an unattended writer, the
  parked "writes from a routine" case. It stays parked.

## 2. Vocabulary: one new kind, `attribute`

The role-shaped facts fit today's kinds: a champion is a `role`, and a blocker
is an `open_question`. What doesn't fit is a standing property of the account.
The proposal is a kind **`attribute`**, with these slots:

| slot | example from the seed |
|---|---|
| `budget_cycle` | "Budget cycle resets in Q1" |
| `procurement` | "Procurement starts once the evaluation convinces them" |
| `billing_model` | "They bill on milestones, not seats" |
| `tooling` | "A legacy stack" |
| `headcount` | (none in the seed notes; the ICP note speaks of employees generally) |
| `deployment` | "Must run on-prem in a container for government work": it decides the offer and the licence (CRO) |
| `pain` | "500,000 invoice rows a week that no team can process": the concrete pain and its deadline, the qualifier that predicted every deal that moved (CRO) |
| `other` | anything else that is a property, not an event |

- **"Who signs"** is a `role` with a new slot, **`signer`**. It is not a
  conflict slot, since an account can need two signatures; `decision_owner`
  stays the only one (CRO).
- **Rules,** following docs/39:
  - an attribute has no `state` and no `due`;
  - two active facts in one attribute slot are **not** a conflict; the newer one
    is shown first, and `supersede_fact` is how one replaces the other;
  - `briefing` gets an `attributes` group, by slot.
- **This is a vocabulary change** (`FACT_KINDS`, `FACT_SLOTS`, the loader
  checks). It changes no existing answer: no existing row can hold the new
  kind, since the loader refuses unknown kinds today.

## 3. Confirmation without a new state

A proposal isn't stored until a person says yes. **There is no `proposed`
state** and no schema column: the proposal lives in the session, and only the
confirmed fact is written. The alternative is a `proposed` state with a confirm
call. That keeps proposals across sessions, but it's a schema change and a new
read path that every fact consumer would have to filter on.

## Decisions for review

1. **The reading runs in the Claude session over MCP.** There is no in-app
   model and no routine; a routine harvest stays parked.
2. **A new kind, `attribute`,** with the slots above, plus a role slot
   `signer`. **Confirmed by the CRO on 6.11.2026, with `deployment` and `pain`
   added.**
3. **Two attributes in one slot are not a conflict.** Newest first; superseding
   one is explicit.
4. **No `proposed` state.** Only confirmed facts are written.

## Acceptance (fail-first, synthetic seed)

The gate can't judge a model's reading; a person does, before anything is
written. So the books test the plumbing and the vocabulary:

1. `harvest_queue(<Nakatomi>)` returns its note, with the facts that already
   cite it (sfa001, sfa008) and the account's other active facts. Every field
   is a lookup, and the request list shows it.
2. `add_fact(kind=attribute, slot=budget_cycle, source doc:<note>)` writes,
   and shows in `briefing` under `attributes` and in the unfold as `said_in`
   the note. An unknown attribute slot is refused, naming the slot.
3. Two `budget_cycle` facts are both listed, newest first, and are not a
   conflict.
4. The seed gains attribute facts for the replica's note (budget cycle,
   procurement, billing model), generated without randomness.
5. `harvest_queue` on the held seed account returns its hold and no notes.
   The same goes for an account whose hold is unclear (two holds).

## Not in this slice

- A scheduled or unattended harvest.
- Notes not linked to an account.
- Harvesting from mail (no mail ingest).
- Training anything on the facts.
