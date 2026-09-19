# 25 · Documents (the knowledge store)

The **Documents** store is where the operator keeps their own writing —
strategy, plans, playbooks, notes, reference — *inside the tool*, tagged and
linked so the agent, the dashboard, and search all ground on it. It replaces
the earlier read-only "Library" (a markdown tree pointed at a folder): same
role (documents the agent grounds on, docs/16, docs/23), but now first-class,
editable, and filterable rather than a passive file mirror.

Rule 2 still holds: a document is *content*, not prediction. Storing, tagging,
linking, and rendering are plumbing; the only ranking over documents is Aito's
text-`_match` in smart search (docs/23), never a Python heuristic.

## The model

A document is an Aito collection row — the journal is the closest cousin
(docs/20), and the write path mirrors it (full-rewrite edits, no `_modify`).

```
documents (collection)
  doc_id          String   id, "dc0007" (seed) / "dc-<ts>" (live)
  title           Text     first heading / given title
  body            Text     the document, markdown
  kind            String   docs | internal            (DOC_KINDS)
  area            String?  sales|marketing|rnd|operations   (DOCUMENT_AREAS)
  topics          String?  free-form ';'-joined topics — the arbitrary-topic axis
  noted_on        String?  ISO date the note is ABOUT — the diary / browse-by-day axis
  company         String?  direct company association (display string)
  company_id      String?  link → companies.company_id (the entity; derived from company)
  stakeholder_id  String?  optional contact link (a person)
  source          String?  provenance (imported file path), else null
  created         String   ISO
  updated         String   ISO
```

The last two axes are the entity-graph notes work (`.ai/tasks/15` Phase 2):
`topics` is the free-form axis the fixed `area` enum can't cover; `noted_on` is
the diary date (the day a note is about, distinct from `created`), so a daily
note is just a document dated to a day — no separate diary table.

Two orthogonal tags, both the operator's:

- **`kind`** — the top-level split. `docs` is shareable/generic reference;
  `internal` is private thinking (strategy, plans). It is the coarse privacy
  and audience signal.
- **`area`** — optional, the same taxonomy as everywhere else
  (`DOCUMENT_AREAS` ⊂ the shared areas: sales, marketing, rnd, operations). A
  generic `docs` note usually has no area; an `internal` GTM plan is `sales`.

**Links** (both optional, on any document, emphasized for sales):

- **`company`** / **`company_id`** — the company as both a display string and a
  first-class **link** to the `companies` entity (`.ai/tasks/15`), derived from
  the string on write/load and kept in step with it. So a note hangs off the
  same company node as its contacts, deals, and touches, and
  `select company_id.name` traverses to the entity.
- **`stakeholder_id`** — a contact, validated against `contacts` on write
  (rule 3: a dangling link raises).

## Surfaces

- **Documents view** (nav): the list, filtered by `kind` / `area` /
  `company` / person, with an **in-dashboard editor** — create, edit, delete a
  document (title + markdown + tags + links) without leaving the tool. This is
  the "keep my documents here" surface.
- **Area views** (Sales / Marketing / R&D / Operations): each gains a
  **Documents** tab showing the documents tagged to that area — the sales rep's
  playbooks and account plans sit beside their pipeline. The Sales tab surfaces
  the company/person link prominently.
- **Smart search** (docs/23): documents are unioned into `search_items` as
  `kind=doc`, so they are searchable and the assistant/agent reach them the
  same way as contacts/deals/journal. One chokepoint feeds all three.
- **Diary / browse-by-day** — `documents.diary()` groups the dated notes
  (`noted_on` set) newest-day-first, narrowable by company / topic / date
  window; `documents.topics()` is the browse-by-topic index (each topic with its
  count). The daily-folder notes the operator kept in Trilium live here.
- **Agent / MCP**: `documents_list` (filters incl. `topic`), `document_read`,
  `document_diary`, `document_topics`, `add_document`, `update_document`
  (both take `topics`/`noted_on`), `remove_document`. The dashboard assistant
  reaches document *content* through `smart_search`, narration-only.

## Getting content in

- **Author in the dashboard** — the editor is the primary path.
- **Import a folder once** — `company-ai documents-import <dir>` walks markdown
  under a directory (path-safe: markdown only, no traversal), taking the first
  `# heading` as the title and optional YAML front-matter (`kind`, `area`,
  `company`, `stakeholder`, `topics`, `noted_on`) as metadata. `noted_on` also
  falls back to an unambiguous `YYYY-MM-DD` in the **filename**, so a Trilium
  daily-note export (`2026-06-14.md`) files itself into the diary without
  editing; `company_id` is derived from `company`. The mapping is
  layout-agnostic — explicit front-matter and a date-in-filename only, no
  folder-name guessing (a repo's folder convention → company/topic mapping is a
  clean follow-up once a real export layout is known). This is how an existing
  private knowledge dir (the old `COMPANY_AI_LIBRARY_DIR`, or a markdown export)
  moves in — run once, then keep them in the tool. Re-import is idempotent on
  the file path (`source`).
- **Import a Trilium tree** — `company-ai trilium-import --db <document.db>`
  (`--dry-run` to preview) reads a Trilium note tree read-only (`trilium.py`),
  converts each note's CKEditor HTML to markdown, and maps `<root>/Companies/<Name>`
  → a company-linked document and `<root>/daily/<YYYY-MM-DD…>` → a dated diary
  document. It creates a `companies` entity row for any new name (so every note
  links), and is idempotent on `source='trilium:<noteId>'`. Real note content
  goes only to Aito, never the repo.
- **Seed** — `data/seed/documents.csv` carries a few synthetic documents
  (both kinds, some with area/company/person) so the demo and booktests have a
  store to render and search.

## Not built here — parked extensions

These are real and worth doing, but each is its own design (rule‑1/2 boundaries
about *who computes what*), so they are parked, not folded in. The schema above
leaves clean seams for them:

- **Vector / semantic search** — embedding-based retrieval over `body`,
  alongside (not replacing) Aito's text-`_match`. Seam: a new ranking source in
  `search.py`; the `documents` rows are already the corpus. Whose embedding /
  where the vectors live is the open question (Aito vs. an external index).
  Proposal: `.ai/tasks/12-vector-and-graph.md`.
- **Entity / graph extraction** — pulling companies, people, and topics out of
  document bodies into a graph that links documents ⇄ contacts ⇄ deals. This
  needs an extraction step (likely the LLM, so it lands behind the `llm.py`
  provider and must stay narration-of-Aito-facts clean, not a new reasoning
  layer). Seam: `stakeholder_id` / `company` are the manual version of exactly
  those edges; extraction would *suggest* them. Same proposal note.

## Definition of done

A document created in the dashboard is immediately: listed under its area tab,
found by smart search, and readable by the agent over MCP — with a booktest
that prints the write, the Aito round-trip, and the search hit (rule 5).
