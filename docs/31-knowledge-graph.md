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

And the neighbourhood can condition a **prediction**, which is the layer above
lookup — the question stops being "which" and becomes "how likely":

```json
{ "from": "deals",
  "where": { "company_id.$refs.contacts.company_id": { "$exists": { "role": "CTO" } } },
  "predict": "won", "select": ["$value", "$p"] }
```

That walks forward from the deal to its account, then **backwards** to that
account's people, and asks whether any of them is a CTO — a fact that exists
nowhere on the deal. Aito returns **31%**, against a **24%** base rate across
all closed deals. This is the one query on the board that a relational database
could not also produce; most of the others are joins in disguise.

### Several facts at once, with the reasons attached

A prediction conditioned on one fact is a thin demonstration. `$why` returns
what each condition did to the number, as a multiplicative lift:

```json
{ "from": "deals",
  "where": { "company_id.industry": "accounting",
             "champion_present": true, "blocker": "none" },
  "predict": "won", "select": ["$value", "$p", "$why"] }
```

→ **71%** (base rate 26%), because `blocker=none` ×1.75, the account's
`industry=accounting` ×1.45, and `champion_present=true` ×1.42. One of those
three lives on the *company*, not the deal, and is only reachable across the
link. `graph.py` flattens the `$why` tree with `aitowhy.lift_factors` — the
same helper the deal close-likelihood already uses — and the view draws each
factor as a bar either side of a midline, since lift is multiplicative and ×2
and ×0.5 are the same size of effect in opposite directions.

**Explaining a reverse-link fact: harvest it onto the node.** Because the
filtered `$exists` form cannot be explained, the "do we know a CTO there?"
fact is also materialised as `companies.technical_contact` at load time, by
walking `companies <- contacts`. As a column it is an ordinary forward path,
so a prediction conditioned on it comes back with its reasons:

```json
{ "from": "deals",
  "where": { "company_id.technical_contact": true, "blocker": "none" },
  "predict": "won", "select": ["$value", "$p", "$why"] }
```

→ **58%** against a 26% base rate, with `company_id.technical_contact=true`
worth **×1.40**. That number — how much knowing a technical buyer is actually
worth — is the thing the live `$refs` form can compute but not explain. The
board keeps both cards: the live reverse-link query, which shows the real
`$refs` syntax, and this one, which shows what the fact is worth.

**`$why` and `$refs` do not combine.** (More precisely: a *bare*
`$exists: true` explains fine; the *filtered* `$exists: {...}` form is what
returns 400.) Adding an explanation to a query whose
`where` contains a reverse link returns a 400 from the explanation formatter,
while the identical query *without* `$why` predicts fine. So a reverse-link
prediction can have the number or the reasons, not both — which is a shame
exactly where the graph is most interesting. Filed upstream; see the sharp
edges below.

### Two traps, both hit while building this

**Target leakage.** The first version of this card conditioned on
`company_id.relationship = customer` and reported a triumphant 50%. It was
meaningless: `relationship` is *derived from deal outcomes* — an account is a
customer precisely because it won a deal — so the label was being fed back in
as the feature. **Never condition a `won` prediction on `relationship`,
`mrr_eur` or `open_deals`.** Those facts are for lookup ("who pays us"), not
for predicting the thing they are computed from. A conditioned probability that
looks too good is usually a feature derived from the answer.

**No signal to find.** The honest replacement barely moved: industry predicted
27% against a 25% base rate. The cause was in the generator — deal outcome
depended only on deal-level features, while a company's industry was rolled at
random per deal, so every company fact was *statistically independent of
winning by construction*. Aito was right to return the base rate. Garbage in,
garbage out: a demo of inference over a graph has to contain something for the
inference to find, so `scripts/generate_seed.py` now plants two account-level
effects (`INDUSTRY_WIN_LIFT`, and a lift for knowing a CTO) and the accounts are
coherent entities that contacts and deals inherit from.

The honest measure of a conditioned prediction is its distance from the
unconditioned one. Measure the base rate before quoting a lift.

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
- **A reload leaves link resolution stale, in both directions, silently.**
  Drop-and-recreate the target and forward paths return zero; reload a referrer
  and the target's `$refs` index returns zero. The rows are fine; the answer is
  just wrong, and looks like "nothing matches". `loaders._reload` now flushes
  both ends of every link it declares, which is why you will not hit this
  through the loaders — but a hand-rolled upload can still walk into it.
- **`$why` cannot explain a `$refs` proposition** — the query 400s in the
  explanation formatter. Predict from a reverse link, or explain a prediction,
  but not both in one query.
- **`orderBy` cannot name a `$refs` path directly**; alias a `$length` in
  `select` and order by the alias.

## Where this goes

The harvested facts are the floor, not the ceiling. The same node could carry
facts harvested from outside the system — the website, meeting notes — and the
predictive layer above it (churn, expansion, win likelihood conditioned on
graph position) is exactly the `predict` form above with a different target.
Both are deliberately *not* built yet.
