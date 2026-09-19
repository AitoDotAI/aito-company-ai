# 22 · The change log

An append-only audit of **what changed** — items created and updated across the
system: a todo created, done, or archived; a deal created, won, or lost; a
routine ticked; an experiment validated; an event decided; a post's result.
Both the operator (via the
dashboard) and the agent (via MCP) write through the same functions, so every
meaningful mutation lands here.

## Shape (`schema.changelog`, one row per event)

`change_id · at (UTC) · entity · entity_id · action · summary · detail`

- **entity**: `todo | deal | touch | routine | experiment | event | post`
- **action**: `created | updated | done | archived | won | lost | logged | validated | invalidated | go | no_go | attended | removed | posted`
- **summary**: one human line ("deal won: Acme Oy → closed_won (100%)")
- **detail**: optional JSON of what changed (e.g. the edited fields)

It's app state, kept in Aito (durable, no filesystem), and — like the other
app-state tables — outside the CSV load/export machinery.

## How it's recorded

`changelog.record(client, entity, id, action, summary, detail?)` is a single
cheap insert (no rewrite). The write functions in `log.py` call it right after
they commit, so recording a change is part of the same operation that made it
(the round-trip booktest proves acting shows up in the log).

## Where it's read

- **Dashboard**: the **Activity** view (Knowledge) — a newest-first feed.
- **Agent (MCP)**: `recent_changes(limit, entity?)`.
- **Assistant**: the `recent_changes` tool, so "what changed this week?" is
  answerable and grounded.
- **Week-prep composer**: `recent_changes` is a `board.READS` entry, so the
  Sunday-prep writer can lean on it.

`changelog.recent(client, limit, entity?)` returns `{changes, count}`, newest
first, optionally filtered to one entity kind.

## The follow-on (parked)

The point of the log is to roll up into **daily / weekly notes** (dated
documents, docs/25) —
"this week: 3 deals advanced, 1 won, 12 calls, 2 experiments validated" — fed to
the assistant as narrative context. That summarizer (a tool-less LLM composer
over a day/week's changes, like the week-prep composer) is proposed in
`.ai/tasks/`, not built yet.
