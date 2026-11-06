# 38 — rep1 → rep2: already done (corrected 6.11.2026)

Status: **nothing to migrate.** Every table on internal is already on Aito's
v2 storage engine. This note first held a plan for moving the tables
(PR #68). The premise was wrong, and the evidence is below so the plan isn't
revived by mistake. Board item td-20261106100502161570.

## The evidence

Read-only, `GET /api/v2/schema/<table>` per table on internal
(2.12.0-dev+11141e6c), 6.11.2026 (`.ai/maintenance/engines_report.py`):

| declared `type` | `engine` | tables |
| --- | --- | --- |
| `collection` | `v2` | 21: assignments, companies, contacts, deal_events, deals, documents, events, search_contexts, search_impressions, search_vectors, todos, tokens, touches, users, web_sessions, web_steps, web_suppressed, web_visitors, and three app tables outside `schema.py` |
| `table` | `v2` | 11: changelog, channels, chat_messages, decisions, experiments, materials, posts, routines, sessions, and two app tables outside `schema.py` |
| `view` | `v2` | search_items |
| any | `v1` | **none** |

## Why it looked otherwise

- `schema.py` declares 26 tables as `"type": "table"`. But
  `AitoClient.create_table` (`src/company_ai/aito.py`) sends
  `{**definition, "type": "collection"}`. So every table our client creates
  is a collection, whatever `schema.py` says.
- Aito itself, given `"type": "table"` on the **v2** schema route, makes a
  table on the **v2 engine** (`type: table, engine: v2`). Only the **v1**
  route makes `engine: v1`. Checked on a throwaway local
  `aito:v2.12.0` (ef016d9b):
  - `PUT /api/v2/schema/t {"type": "table", ...}` → `{"type": "table", "engine": "v2"}`;
  - `PUT /api/v1/schema/t` (same body) → `{"type": "table", "engine": "v1"}`.

  The 11 `table`/`v2` tables on internal came through some route other than
  our current client (an older client, or a `migrate`, which also leaves
  `table`/`v2`).
- aito-core's docs call `table` rep1/TableDb. That gap is filed as
  td-20261106175554336673.
- The first probe for the plan created its "rep1" tables through our client,
  so it compared v2 with v2. Its "doc differences" (`$match` and upsert on
  rep1) were artifacts, and weren't filed.

## What follows

1. `schema.py` says `"collection"`, matching what is created. That's code
   only: the payload sent is unchanged, and a book pins it.
2. What still needs an answer from aito-core (td-20261106175554336673): does
   `table`/`v2` behave exactly like a collection (links to and from
   collections, `$patterns`, in-place alter, `_evaluate` kinds)? Until it
   does, treat the 11 as v2 but unverified for collection-only features.
   Recreating one as a collection would be a schema change on internal, and
   that is Antti's yes.
3. docs/37's "links can't cross rep1/rep2, and our tables are rep1" premise
   was wrong for the same reason. Corrected there.
4. Upsert by `primaryKey` (the duplicate-on-resend hazard,
   td-20261106110308568348) doesn't depend on any of this. Declaring a key is
   its own schema decision.

## Method lesson

Check the `engine` field before comparing engines. A declared `type` is
not evidence of the storage engine.
