# 31 · The knowledge graph

An agent kept failing at questions a salesperson answers instantly — *who
actually pays us? what is their MRR? which of these are just prospects? who do
we know at the accounting ones?* Not because the data was missing, but because
it was **unreachable**: the company row held a name and nothing else, and every
fact lived on the rows around it.

This is the fix, in two halves: give the company node facts, and walk the links.

## Half one — the node holds facts

`companies` used to be `{company_id, name}`. It now carries what we actually
know about an account:

| column | meaning |
|---|---|
| `industry` | the modal `segment` across its contacts (or deals) |
| `relationship` | `customer` · `prospect` · `lost` · `none` |
| `country` | the modal country across its contacts |
| `mrr_eur` | won deal value / 12 — 0 when nothing is won |
| `open_deals`, `contact_count` | how much is in flight, how well we know them |

All of it is **harvested at load time** (`loaders.companies_from_csvs`) from the
contacts and deals that already link here — not authored, so it cannot drift
from the rows it summarises. `relationship` comes from deal outcomes: a won deal
makes an account a customer, an open one a prospect, only-lost deals `lost`,
and no deals at all `none`. This is load-time featurization, the same move as
`derive_contact_funnel`; nothing is predicted here (rule 2).

## Half two — the links are walkable

The company is the hub, and three tables point at it:

```
companies  <--company_id--  contacts  <--contact_id--  touches
           <--company_id--  deals
           <--company_id--  documents
```

Aito walks that edge in **both** directions, which is what turns a join into a
query:

**Forward** (child → parent) is a dotted path. From a contact, its account's
own columns are `company_id.relationship`, `company_id.industry`:

```json
{ "from": "contacts",
  "where": { "role": "CFO", "company_id.relationship": "prospect" },
  "select": ["name", "company", "country"] }
```

**Reverse** (parent → children) is `$refs.<table>.<fk>` — on a company,
`$refs.contacts.company_id` is the set of contacts pointing at it. `$exists`
filters that set; `$length` counts it:

```json
{ "from": "companies",
  "where": { "$refs.contacts.company_id": { "$exists": { "role": "CTO" } } },
  "select": ["name", "industry", "relationship"] }
```

And a fact on the far side of a link can condition a **prediction**, which is
the layer above lookup — the question stops being "which" and becomes "how
likely":

```json
{ "from": "deals",
  "where": { "company_id.relationship": "customer" },
  "predict": "won", "select": ["$value", "$p"] }
```

That returns **50%**, against a **25%** base rate over all deals: a deal at an
account that already pays us is worth about two at a new one. The condition is
a fact that exists only because it was harvested onto the node — there is no
`relationship` column on `deals` to filter by.

Pick this kind of example carefully. `company_id.industry: "accounting"`
predicts 27% against the same 25% base rate — a number that *looks* decisive
at 73%/27% while saying essentially nothing. The honest measure of a
conditioned prediction is its distance from the unconditioned one, so measure
the baseline before quoting a lift.

## The surface

`src/company_ai/graph.py` holds the questions, one Aito query each; `/api/graph`
runs them; the **Knowledge graph** view renders each question beside the query
that answered it, because the claim being made is that the two are nearly the
same sentence.

## Sharp edges

This is a **young corner of Aito**, and the limits are worth knowing before you
extend it. They are not bugs in this repo:

- **An unresolvable dotted field matches nothing, silently.** `company_id.NOPE`
  returns `total: 0` rather than raising, so an empty graph result is ambiguous
  between "no such rows" and "no such field". Decompose a surprising zero before
  believing it.
- **`$refs` needs the FK**: `$refs.contacts.company_id`, never `$refs.contacts`.
- **Inside `$exists: {…}` only equality works.** Range and match operators have
  to sit on a forward dotted path in the outer `where`.
- **Don't `$and` two `$refs` `$exists` conditions** — that combination is known
  broken upstream. One `$exists: {…}` object with several keys is fine.
- **Two-hop `$exists: {"link.attr": v}` assumes the target key is named `id`.**
  Ours are `company_id` / `contact_id`, so that form does not work here.
- **`$refs` is materialised eagerly** over the whole table regardless of
  `limit` — fine at this size, not a plan for millions of rows.
- **`orderBy` cannot name a `$refs` path directly**; alias a `$length` in
  `select` and order by the alias.

## Where this goes

The harvested facts are the floor, not the ceiling. The same node could carry
facts harvested from outside the system — the website, meeting notes — and the
predictive layer above it (churn, expansion, win likelihood conditioned on
graph position) is exactly the `predict` form above with a different target.
Both are deliberately *not* built yet.
