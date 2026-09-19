# 20 · Journal — RETIRED (folded into Documents, docs/25)

**Status: retired (2026-08-17, `.ai/tasks/15` Phase 2d).** The journal was a
separate `journal` table — a dated rolling-memory diary. It has been **folded
into the Documents store** (docs/25): a document now carries a `noted_on` date
(the diary axis) and free-form `topics`, so "a dated note the agent writes and
recalls" is just a document dated to a day. One store, not two.

What moved where:

- **The diary / browse-by-day** → `documents` with `noted_on` set;
  `documents.diary()` groups by day, `document_diary` (MCP) reads it.
- **Writing a memory** → `add_document(..., noted_on=…, topics=…)`; the routines
  runner (docs/18, rule 1c) records its narration as a dated document.
- **Recall / search** → documents are in the `search_items` union already
  (docs/23), so the same smart search reaches them.
- **Existing entries** → the one-shot `migrate-journal` CLI folds every journal
  row into a document (`date`→`noted_on`; `kind`/`tags`/deal-link→`topics`;
  links carried over). Run once on an instance that still has the table, before
  it is dropped.

Nothing here is a live surface any more — see **docs/25 (Documents)** for the
model, the diary/topic surfaces, and the importer.
