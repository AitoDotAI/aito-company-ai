# 16 · The dashboard assistant

A right-side chat panel where you can ask the system questions — "how's my
pipeline?", "who should I call at 12:15?", "which experiments paid off?" — and
get a grounded answer. It exists for two reasons the operator asked for: a
fast way to **exercise the tool surface** (every reply shows the tools it
ran), and **mobile** use, where clicking through tabs is slower than asking.

## Why this is named an agent loop (and fenced as one)

Unlike the board composer (a writer, no tools — `docs/15`), the assistant
*does* run a bounded, server-side tool-calling loop. That is an agent loop,
and CLAUDE.md rule 1 names it as the second scoped exception. It earns the
exception only because it is fenced hard:

- **Read-only tools.** The model may call only the tools in
  `src/company_ai/assistant.py` (`who_to_call`, `deal_pipeline`,
  `experiment_board`, `funnel`, `segment_360`, `score_post`, `todos_now`,
  …) — each an existing function MCP and the dashboard already use. No new
  logic, no heuristics, and **no writes**. The model picks *which* tool and
  narrates the result; it never computes a ranking, score, or prediction
  (rule 2 still owns all of that). Every internal number it states comes from
  a tool result.
- **Two non-Aito tools: `web_search` and `fetch_page`.** The only reads that
  are not Aito-backed. `web_search` (`websearch.py`) finds *external* facts
  Aito cannot hold — company news, market moves, a person's current role — and
  returns ranked results (title, url, snippet). `fetch_page` (`webfetch.py`)
  then reads one page by URL and returns its title + readable text. Both are
  still reads and still narration-only: they never score or predict, and they
  are fenced off from internal numbers (those stay in Aito). `web_search` is
  **off unless a search key is configured** (provider swappable by env,
  `Config.search_*`, Brave today); `fetch_page` is keyless and on by default
  but **SSRF-guarded** — every URL and every redirect hop must resolve to a
  public address, so loopback/private/link-local/metadata targets are refused
  (it runs server-side on Azure, where `169.254.169.254` is the instance
  metadata endpoint). Each is advertised only when available. Because the
  query and the fetched URL leave the machine, they carry a privacy note —
  see `docs/06`.
- **One registry, tailorable.** Every tool — Aito-backed and web — lives in a
  single `TOOLS` list in `assistant.py`. Each `Tool` carries its name, schema,
  a uniform `run(ctx, args)`, an optional `available(ctx)` gate, and an
  optional system-prompt `note`. Adding a tool is appending one entry; nothing
  in the loop changes. A fork can curate the surface with
  `COMPANY_AI_ASSISTANT_TOOLS` (a comma-separated allowlist) — the assistant
  then exposes only those names, intersected with what's available. This is
  the seam meant for reuse; it does not loosen the fence (everything here is
  still a read).
- **Bounded.** The loop runs at most `MAX_ROUNDS` tool rounds, then forces a
  final answer. No runaway.
- **No silent failure (rule 3).** A tool error — bad argument, unknown tool
  the model hallucinated — is fed back to the model as the tool result and
  recorded in the trace, never swallowed or hidden.
- **Swappable model.** Same provider as the composer (`llm.py`,
  `Config.llm_*`); gpt-5-mini for testing, a high-end model later, by env
  alone. No key → loud failure, never an empty answer.

## The shape

```
browser ──POST /api/assistant/chat {messages}──▶ assistant.run_turn
                                                   │  (system prompt + tool specs)
                                   ┌───────────────┴───────────────┐
                                   ▼                               ▼
                            llm.chat(messages, tools)        execute the chosen
                            → tool_calls? ───────────────▶   Aito-backed tool,
                                   ▲                          feed result back
                                   └──────── loop (≤ MAX_ROUNDS) ──┘
                                   ▼
                            final reply + trace  ──▶  rendered right-side,
                                                      tools shown as chips
```

The **trace** (which tools ran, with what args, ok/failed) is returned to the
client and shown beneath each reply — that is what makes the panel double as
a live tool-contract tester.

## Surfaces

- **Backend**: `assistant.run_turn(history)` and `POST /api/assistant/chat`.
- **Frontend**: the **Ask** button (top-right of any view) opens the panel
  (`frontend/src/assistant.jsx`); collapses to a full-width overlay on mobile.
- **Tests**: `book/test_assistant.py` drives the loop with a scripted fake
  LLM (grounding, argument threading, error-surfacing, the round bound) and
  scripted web backends (search + fetch ground on results, their errors
  surface, each is advertised only when available), plus unit checks of the
  fetch SSRF guard and the HTML→text extractor;
  `frontend/src/assistant.test.jsx` covers the chat UI.

## Deliberately not here

No writes from the assistant (logging a touch, advancing a deal) and no
second model surface. Both are parked, not built — an LLM autonomously
mutating the real pipeline is a bigger decision than this panel, and the
operator can opt into it explicitly later (`.ai/tasks/` if/when proposed).
