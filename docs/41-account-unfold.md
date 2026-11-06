# 41 — Unfold one account, with every fact traced to its record (spec for td-20260926220007895967)

Status: **built (6.11.2026); spec approved in #81.** Parts 1 and 2 of the ticket: the entity unfold,
and provenance. Part 3, harvesting facts *out of* meeting notes, gets its own
ticket once these exist, as the ticket says.

## What exists already

The pieces are mostly built, in three places that don't meet:

- **`graph.network()`** (docs/31) draws every account at once. It filters by
  industry, relationship or country, and a name lookup keeps the matches with
  their one-hop neighbours.
- **`companies.detail()`** (`company_detail`) gives one account's harvested
  facts plus its contacts, deals and notes, as lists.
- **`companies.briefing()`** (docs/39) is the call-prep read of one account:
  open deals, stakeholders, touches, notes, todos and the account facts, each
  with its `source`.

So the unfold is not new data. It is **one account as a graph**: those rows as
nodes and links, with every fact pointing at the record it came from.

## 1. The unfold: `graph.network(focus=company_id)`

`network()` gains one argument, `focus`. With it, the nodes are:
- the company;
- its contacts, deals and documents (by `company_id`, as today);
- its touches;
- its **active account facts** (docs/39), as a new node kind, `fact`.

Each fact node links to:
- its stakeholder, if it has one;
- **the record named by its `source_kind` and `source_id`**: a touch, a
  document, or a mail that is shown as a label because it isn't stored. The
  ticket's "says who?" is that link.

The rules:
- **Superseded facts are left out**, as in search (docs/40).
- **A hold is drawn but carries no detail beyond `on_hold`.** It's the same
  fail-closed reading as `briefing`.
- **A `source_id` that resolves to nothing is drawn as a dangling source**,
  named, not hidden (rule 3 at read time: shown, since the row is already
  written).

There's no new query shape: one query per table filtered on `company_id`,
the same as `detail`.

### Sources must resolve before they can be traced

This was found while writing this spec. `source_id` is free text today
(docs/39: "the mail, document, touch or note id"), and **none of the 12 seed
facts resolves to a stored record**. Their ids are references like
`call-seed-0111` and `doc-seed-split`. So the join the ticket assumes exists
only on paper. The proposal:

- **Resolve by kind:**
  - `doc` → `documents.doc_id`;
  - `touch` → `touches.touch_id`;
  - `call` → a touch, when the id is one;
  - `mail`: no mail is stored (mail ingest is out of scope), so it's a
    labelled external reference;
  - `antti`: an operator statement, labelled as such.
- **The seed's `doc` and `touch` facts point at real seed records**
  (`generate_seed.make_facts`), so the book proves the join. A fact whose
  source doesn't resolve still shows, as a named dangling source.
- **Not in this slice:** making `add_fact` refuse an unresolvable `doc` or
  `touch` id. That turns a write that works today into an error, so it's
  Antti's call (decision 5).

- **MCP:** `graph_search(focus=...)`.
- **API:** `/api/graph/network?focus=...`.
- **Dashboard:** the Knowledge graph view's side panel gets an "Unfold"
  button that re-centres on the company.

## 2. Provenance for the harvested node facts

`industry`, `relationship`, `country` and `mrr_eur` are harvested at load
time (docs/31). Today they're shown with no trace. The unfold gives each one
its **basis: the rows it was derived from**. The rule is already fixed in
`loaders.companies_from_csvs`; this only shows which rows it ran over.

- **`industry` and `country`:** the contacts, or the deals for `industry`,
  whose value was the modal one, as "3 of 4 contacts", each linked.
- **`relationship`:** the deals whose outcome decided it. For example, the
  won deal that makes it a customer, or "no deals" for `none`.
- **`mrr_eur`:** the won deals summed.

**The basis is read live in the unfold** (the same `company_id` queries), not
stored. The alternative is a column written at load, which can drift from the
fact it explains, the drift docs/31 harvested to avoid. It's a count over rows
already fetched for the unfold, so no ranking (rule 2).

## 3. One deal's `$why`, inside the unfold

A deal node opens to `deals.close_likelihood` for its profile: the existing
P(won) + `$why`, learned from closed deals. **No new conditioning.** In
docs/31's two traps:
- conditioning on `relationship` leaks the outcome;
- `industry` carried no signal on the seed.

So neither is added to the evidence. If a neighbouring fact should move a deal,
that's a before/after numerical test on the seed first (rule 4), and a separate
change.

## Decisions for review

1. **The unfold is a focus mode of the existing graph,** not a new view or a
   new MCP tool. The alternative is a separate `account_graph` tool.
2. **Account facts become graph nodes** of kind `fact`, linked to their source
   record. The alternative is to list them in the side panel only.
3. **The basis is read live,** not stored at load.
4. **The deal `$why` is reused unchanged:** no graph features are added to its
   evidence in this slice.
5. **Unresolvable sources are shown, not refused.** Validating `doc` and
   `touch` ids in `add_fact` is proposed, for Antti, separately.

## Acceptance (fail-first, synthetic seed)

1. `network(focus=<replica>)` returns:
   - the company;
   - exactly its contacts, deals, documents and touches;
   - its active facts.

   No superseded fact appears, and no node belongs to another company.
2. Every fact node links to a node, an external reference or a named dangling
   source. A seed fact whose source is a document or a touch links to that
   record. Before the seed change, none did.
3. `industry`, `relationship`, `country` and `mrr_eur` each carry a basis whose
   rows reproduce the harvested value. The book recomputes the value from the
   basis and compares.
4. A hold fact appears as `on_hold`, with no more detail than `briefing` shows.

## Not in this slice

- Harvesting facts out of meeting notes (part 3; its own ticket).
- New predictive features from graph position.
- Unfolding a contact or a deal as the focus.

## Decision 5, as settled in review (CPO, 6.11.2026)

`add_fact` accepts a fact whose `doc` or `touch` source names nothing, as
before, and returns `warnings: ["source <kind>:<id> not found"]`. The unfold
draws it as dangling. **Refusing an unresolved source** is kept as an option
for Antti, since it would turn a write that works today into an error.

## Built (6.11.2026)

- **`graph.network(focus=company_id)`**, with MCP `graph_search(focus=)` and
  `/api/graph/network?focus=`. It runs one query per table on `company_id`;
  touches go through `contact_id.company_id`. Without `focus` the graph is
  unchanged, and `touch` and `fact` are refused as kinds.
- **The source rule** (`facts.source_of`):
  - `doc` and `touch` sources are linked or dangling;
  - a `call` is linked when its id is a logged touch, otherwise external,
    since calls needn't be logged;
  - `mail` and `antti` are external.

  A source record on another account is still drawn, as the fact's record.
- **One harvest rule.** `loaders.harvest(contacts, deals)` returns the node
  facts and their basis. The load uses it, giving byte-identical rows on the
  seed, and so does the unfold. The unfold runs it over the live rows, so a
  write since the load shows as `matches: false` and is not hidden: the book
  adds a deal to a `none` account.
- **Seed:** the replica's `doc` facts point at its document, and its `touch`
  fact at its stakeholder's first touch. Only `facts.csv` changed.
- **Dashboard:**
  - the company panel has "Unfold this account";
  - the unfolded view shows each harvested fact's rows, the hold and every
    fact's source;
  - "← Whole graph" goes back.
