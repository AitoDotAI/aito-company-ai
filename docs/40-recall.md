# 40 — Recall over facts, and thin documents (spec for slice 3 of td-20261103224048158692)

Status: **spec, for review.** It implements parts (c) and (d) of the design
Antti approved on 3.11.2026, on top of the facts collection (docs/39). Mail
ingest and T2 stay out. The two schema columns in §4 are a schema write on
internal, which is Antti's yes at rollout.

## 1. Facts in the search index

`search_items` (docs/23) gains a fifth source: active facts, `kind: fact`,
`source_id: fact_id`, with the statement as both title and content. Superseded
facts aren't searchable. If a union part can't take a `where` (to be checked
first, on the test engine), superseded facts are included but every hit carries
`superseded_by`, and `search.serve` keeps them out of the results it shows.
That is a filter on a recorded field, not a ranking.

Facts use the same ranking as everything else in the index: Aito's text match,
then the click-trained `_recommend` (docs/23). Nothing new is ranked in Python.

## 2. Embeddings: at reindex only (Antti, 6.11.2026)

Facts get vectors when `reindex_search` runs with embeddings, the same path as
documents today. **There is no per-write embedding**, so no new spend path.
A fresh fact is found by text search at once, and semantically after the next
reindex.

## 3. Supersede candidates on `add_fact`, for confirmation only

`add_fact` returns `supersede_candidates` with the new row. These are the
**active facts of the same company and kind** (for a `role`, of the same
slot too), other than the new one. They are in **Aito's order**: a `_query`
`$match` of the new statement's terms over `statement`, ordered by `$p`, as in
`search.search`. Candidates that share no term follow in `valid_from` order.
At most 5.

They are **never applied**. The caller confirms by calling `supersede_fact`.
The book shows that adding a second decision-owner fact lists the first as a
candidate, and leaves it active.

## 4. Marks: the existing impressions loop, extended

The design asks for a contexts/marks pair (context keys, item, position, used,
flagged_wrong), logging only for now. `search_contexts` and
`search_impressions` (docs/23) already are that pair: a row per search served,
and a row per item shown, with its position. So no new tables:

- `search_impressions` gains `used` (Boolean, nullable) and `flagged_wrong`
  (Boolean, nullable): a shown item the reader actually used, or marked as
  wrong.
- `search_contexts` gains `company_id` (String, nullable, **not** a link,
  like the other ids there): the account a call-prep search was for.
- An MCP tool `mark_item(context_id, item_id, used | flagged_wrong)` and the
  API route sit beside `record_click`. They write one impression row in place.

**Logging only.** The `_recommend` ranking keeps training on `clicked`.
Training on `used` and `flagged_wrong` is the later step the design names, and
isn't built here.

## 5. Thin documents: under 500 characters (Antti, 6.11.2026)

`THIN_DOC_CHARS = 500`. A document whose body is shorter carries
`thin: true` wherever it's listed:
- search hits;
- `briefing` notes;
- the documents feed.

On internal (6.11.2026) that marks 17 of 247 documents. The flag is
**formatting**: it doesn't hide, demote or re-rank anything (rule 2).

The design says "at index time". A view can't compute a length, so the flag is
worked out when a row is read, from the body that's already fetched. That needs
no column and no schema change.

## Acceptance (fail-first, synthetic seed)

1. A distinctive fact statement is found by `search` as `kind: fact`; a
   superseded one isn't.
2. `add_fact` of a second decision owner returns the first as its top
   candidate, which stays active until `supersede_fact`.
3. `mark_item` records `used` and `flagged_wrong` on the impression shown,
   and the next served ranking is unchanged by them.
4. A seed document under 500 characters is `thin: true` in search, briefing
   and the feed, and keeps its rank.

## Not in this slice

Training the ranking on `used`/`flagged_wrong`, per-write embeddings, mail
ingest, T2, and T1-live (which waits for the CRO's real facts).

## Built (6.11.2026)

- **Superseded facts are kept out inside the query.** On 2.12.0 a union part
  can't filter: `where: {superseded_by: null}` on a part returned no rows,
  and `$exists` answered 500. So `search_items` holds every fact, and
  `search.search` adds `$not` on the superseded fact ids to its `where`.
  Aito's top N is then N active items, so a page is never short (CPO review
  of #78). The vector path over-fetches, and drops superseded ids before
  truncating.
- **Marks are written on the shown impression in place** (`_write_row`).
  `record_click` appends a row instead, but an appended unclicked row would be
  a new negative example for the click-trained `_recommend`, and marks must
  not move the ranking. The book shows the next serve's order is unchanged.
- **Every seed note is under 500 characters** (the synthetic notes are
  short), so all of them read thin in the seed. The book adds one
  real-length note for the not-thin case.
- **The code can reach an instance before its schema.** Aito 2.12.0 accepts
  a row with an unknown field and drops the value, so a plain search sends no
  `company_id` at all, and a search for an account or a mark refuses with
  "schema not applied: ... run create-schema" rather than losing what it was
  given. A book runs this against tables without the new columns.
- **The marks book trains the ranking first.** A click turns `_recommend` on,
  and the order after the marks is compared with the click-only order. A mark
  that appended a row instead fails it (checked by mutation).
- MCP `mark_item`, `search(..., company_id)`, API `POST /api/search/mark`.
  `add_fact` returns `supersede_candidates`. Fact writes refresh the index.
