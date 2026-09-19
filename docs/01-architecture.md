# Architecture

## The sentence

The morning brief is three MCP calls and a prompt.

## The diagram

```
Claude session (Code or Desktop)     reasoning: composes the brief,
        |                            drafts openers, takes log commands
        |  MCP (stdio)
        v
aito-company-ai MCP server           thin tool layer, zero logic
        |  HTTP
        v
Aito instance (docker)               intuition: ranking, similarity,
        ^                            calibrated confidence, learning
        |
   loaders (CLI)                     rolodex + outcome log -> Aito tables
```

## Components

**MCP server** (`src/server/`). Tools, each a thin wrapper over one Aito
call or one write:

- `who_to_call(window, top_n)` -> spec in `03-morning-brief.md`, query 1
- `opener_context(contact_id)` -> query 2
- `what_changed()` -> query 3
- analytics reads: `segment_360`, `funnel`, `score_post`, `deal_pipeline`,
  `todos_now`, `todos_area`, `documents_list`, `document_read`
- writes: `log_touch`, `log_decision`, `log_deal_update`, `complete_todo`
- ingest (the agent populates the pipeline by talking to the operator):
  `add_contact`, `add_deal` -> validated like a CSV load, written to the live
  Aito instance (never to seed)
- `predict(table, where, predict_field)` -> generic escape hatch for ad-hoc
  questions asked through Claude

The server also exposes a `populate` **MCP prompt** — instructions the agent
can pull on demand for turning what the operator says into these tool calls,
with the privacy boundary spelled out (real data goes to Aito, not the repo).

**Loaders** (`src/loaders/`, exposed as CLI). `load-rolodex` and
`load-touches`: idempotent upserts from the configured data path, or from
`data/seed/` with `--seed`. Row counts in must equal row counts loaded;
anything else asserts.

**Brief prompt** (`prompts/morning-brief.md`). Instructs a Claude session
to call `what_changed`, then `who_to_call` for the current window, then
`opener_context` per queued contact, and emit a brief that fits one phone
screen: follow-ups first, then the call queue with name, why (with `$p`),
and a suggested opener angle.

**`brief --no-llm`** (CLI). Prints the raw results of the three queries
without any model in the loop. Exists so the deterministic core is
booktestable and so the system degrades gracefully to "still useful
without Claude."

## Why no framework

The intelligence in this system is split between two parties that both
already exist: the LLM reasons, the database infers. A framework would add
a third place for behavior to live, which is exactly where unreviewable
logic accumulates. Plumbing is the only code this problem actually needs.

## Configuration

`.env` (never committed): `AITO_INSTANCE_URL`, `AITO_API_KEY`,
`COMPANY_AI_DATA_DIR` (absolute path to the private dataset, outside the
repo). `.env.example` documents all three.
