# Privacy

## The split

This repository is built to be publishable at any moment. Therefore:

- The repo tracks code, schema, prompts, docs, and **synthetic** seed data
  only.
- The real dataset (names, phone numbers, companies, notes) lives outside
  the tree at `COMPANY_AI_DATA_DIR` (see `.env.example`), and is read by
  the loaders at runtime.
- Phone numbers and email addresses are never stored in seed data at all;
  seed rows carry `phone_present` / `email_present` booleans only.
- `.env` is gitignored; `.env.example` carries no secrets.

## What leaves the machine (LLM + web search)

Two app surfaces call an external service, so be deliberate about what they
see:

- **The LLM** (board composer, dashboard assistant — `llm.py`) receives the
  messages and the Aito tool results it needs to write prose or answer. On a
  real deployment that is your configured provider (e.g. Azure OpenAI); pick
  one whose data terms you accept, since real pipeline figures pass through it.
- **`web_search` / `fetch_page`** (the assistant's two non-Aito tools —
  `websearch.py`, `webfetch.py`, `docs/16`) reach the public web. `web_search`
  sends the **query text** to the search provider (Brave by default; off
  unless a key is set); `fetch_page` sends a **GET to the URL** being read
  (keyless, on by default; disable with `COMPANY_AI_WEB_FETCH=off`). The
  queries and URLs are the operator's own; keep real, non-public specifics out
  of them the same way you would out of any web request. `fetch_page` is
  SSRF-guarded to public addresses so it can't be steered at an internal or
  metadata endpoint. Results/pages come back as public web content and are not
  stored.

Neither surface sends the private dataset wholesale; they send what a given
turn needs. The predictive store (Aito) is separate and governed by the split
below.

## Two instances, one rule: synthetic stays off real

There are two kinds of Aito instance, and they must not cross:

- **real data** → a hosted instance (e.g. `aito.example.com/db/aito`),
  selected via `COMPANY_AI_ENV=.env.aito`. Real contacts/deals live only
  here and in the private `COMPANY_AI_DATA_DIR`, never in the tree.
- **dev / tests / synthetic seed** → a **local** Aito (`localhost`), the
  default `.env` / `.env.local`.

The dangerous direction is synthetic-into-real (it silently overwrote a
real load once). Two guardrails enforce the boundary:

- **Legible target.** Every writing command (`create-schema`, `load-*`,
  `clear`, `log`, `complete`) echoes `→ aito: <host>` before acting, and
  the MCP server prints its target to stderr at startup. The db is never
  chosen silently.
- **Seed guard.** `load-* --seed` refuses to run against a non-local
  instance unless `--force` is given. Loading *real* data (`--dir` or
  `COMPANY_AI_DATA_DIR`) into the hosted instance is allowed; pushing
  *synthetic* seed there is not, without an explicit override.

To bring real data in and leave the rest honestly empty, load what you
have and `company-ai clear <table>` the rest (e.g. `clear sessions`).
`company-ai export <table> --dir <path>` dumps a table back to a
re-loadable CSV (Aito → files) — the backup half of the private dataset,
writing the loader's input columns so it loads straight back.

## Diagnosing & migrating an instance

`company-ai doctor` is a read-only health report: the instance build, and
how its schema compares to the code (missing/extra tables and columns, row
counts). It answers "is this instance behind?" without guessing — run it
with `COMPANY_AI_ENV=.env.<instance>` against any instance.

There are three distinct "migrations", do not confuse them:

- **Schema drift** (instance missing tables/columns the code added) →
  `create-schema`. Non-destructive: it adds the missing tables and columns
  in place and never drops data. This is the common case and the only fix
  needed when `doctor` reports drift on a populated instance.
- **Server too old** (API behaviours differ) → not a repo operation;
  provision a newer instance from Aito.ai. `doctor` prints the build so you
  can compare.
- **Move to a fresh instance** → `export-all --dir <dir>` from the old
  instance, point the env at the new one, `create-schema`, then
  `load-all --dir <dir>`. ⚠ `load-all` drops-and-reloads each table it finds
  a CSV for, so never run it against a populated real instance with seed
  data — that is the synthetic-into-real direction the seed guard refuses.

## The check

Before any commit, and as a booktest:

- grep tracked files for anything matching real contact names, phone
  number patterns, or non-public company references
- assert `data/seed/` contains only entities from the synthetic namespace
  (fictional companies and people; the seed generator documents the
  namespace)

If a leak is ever committed, the remedy is history rewriting plus secret
rotation, not a deleting commit. Cheaper to grep first.

## Why this is structural, not procedural

The privacy split is enforced by where data lives, not by remembering to
be careful. The loaders cannot accidentally commit the private directory
because it is outside the repository; the seed data cannot leak real
contacts because real contacts never had a path into it.
