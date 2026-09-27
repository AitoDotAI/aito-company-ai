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

**The same fact, harvested onto the node.** `companies.technical_contact` is
"do we know a CTO there?" computed at load time by walking
`companies <- contacts`. It predates Aito 2.10.3, when a filtered `$refs`
could not be explained and materialising the fact was the only way to get a
reason out of it. The live form explains itself now, so the column is no
longer a workaround — it is just a fact worth having on the node, because
filtering and browsing by it needs no traversal at all:

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

Link support is young, and it moves. Everything below was re-probed against
**Aito 2.10.3** (built 2026-09-27); the list shrank sharply from the day before,
so re-check rather than trusting it.

**Fixed in 2.10.3** — these were real and are not any more:

- An unresolvable linked path now **raises**, naming the field and listing the
  valid ones, instead of silently matching nothing. This was the dangerous one:
  a typo'd path returned `total: 0`, indistinguishable from "no rows match", so
  a confident, correct-looking zero could reach a dashboard or an agent answer.
- `$why` **explains a filtered `$refs`** proposition. Before, a reverse-link
  prediction could have the number or the reasons, never both — which is why
  `technical_contact` is also harvested onto the node.
- The two-hop `$exists: {"link.attr": v}` form works with a link target whose
  key is not named `id` (ours are `company_id`, `contact_id`).
- `$and` over two `$refs` `$exists` conditions returns a result.

**Still true:**

- **`recommend` over a linked path 500s** (`"internal": "None.get"`), so "which
  account property most drives a win" has no direct spelling; condition a
  `predict` on the neighbourhood instead.
- **Inside `$exists: {…}` conditions are equality only** — now a named
  restriction rather than a crash. Range and match operators belong on a
  forward dotted path in the outer `where`.
- **`orderBy` cannot name a `$refs` path directly**; alias a `$length` in
  `select` and order by the alias.
- **`$refs` is materialised eagerly** over the whole table regardless of
  `limit` — fine at this size, not a plan for millions of rows.
- **Link resolution goes stale after a reload, in both directions, silently.**
  `loaders._reload` flushes both ends of every link it declares, which is why
  you will not hit this through the loaders; a hand-rolled upload still can.
- **Cross-table priors want a rep2 collection.** Our tables are declared
  `type: "table"`; filtering works regardless, and how much predictive signal a
  rep1 target contributes is still unconfirmed.

## Where this goes

The harvested facts are the floor, not the ceiling. The same node could carry
facts harvested from outside the system — the website, meeting notes — and the
predictive layer above it (churn, expansion, win likelihood conditioned on
graph position) is exactly the `predict` form above with a different target.
Both are deliberately *not* built yet.
