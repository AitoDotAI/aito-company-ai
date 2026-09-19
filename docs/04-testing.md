# Testing

## Approach

Review-driven regression testing with
[booktest](https://github.com/lumoa-oss/booktest): tests print the Aito
request, the raw response, and the derived output as snapshots that a human
reviews and accepts. A changed snapshot is the review artifact. This is the
same philosophy the company applies to all ML and LLM behavior: AI conduct
should be testable and reviewable, including this repo's.

## Datasets

- `data/seed/`: the synthetic standard dataset. Large enough for plausible
  inference (~50 contacts, ~150 touches).
- `data/seed_tiny/`: deliberately small (~10 contacts, ~15 touches), kept
  to make cold-start behavior visible. The system must produce sane,
  non-crashing, honestly-uncertain output here; this is a feature gate,
  not an edge case.

## Gates

1. **Loader gate:** rows in equals rows loaded, per table, exactly.
   Any discrepancy asserts with the offending rows.
2. **Query gate:** the three brief queries produce reviewed snapshots on
   both datasets.
3. **Round-trip gate (sacred):** log a touch, re-run query 1, and the
   snapshot shows the queue changing in response. If this gate is red,
   the product does not work, whatever else passes.
4. **Inference-change gate:** any change touching queries or schema is
   accepted on before/after prediction output, not on performance numbers.
   A change that "speeds things up" while altering predictions
   unreviewed is a defect.

## Conventions

booktest configuration and snapshot layout follow the conventions of the
company's other repos (booktest.ini at root, `book/` for tests, snapshots
committed). Run the full suite before any commit touching queries, schema,
or loaders.

## Frontend tests

The dashboard's pure frontend logic — the markdown reader and the `api`
fetch helpers — is covered by [Vitest](https://vitest.dev) (jsdom +
Testing Library), in `frontend/src/*.test.{js,jsx}`. This is deliberately
narrow: booktests own everything that touches Aito (the React views render
those results, they don't compute them), so the frontend tests guard only
the client-only logic booktests cannot — parsing, query-string building,
error surfacing. The markdown suite exists because a renderer bug once
hard-froze the Library (a parse loop that failed to advance); a hang now
fails a test on timeout instead of wedging a browser.

Run with `./do test-ui` (or `cd frontend && npm test`); needs the npm
dev-dependencies (`./do install`).
