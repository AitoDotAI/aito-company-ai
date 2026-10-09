# Two sides of the same brain

One Aito instance holds the intuition — the ranking, the
probabilities, the causes and levers learned from outcome history. It is
exposed two ways, to two kinds of user:

```
                         ┌──────────────────────────┐
       SIDE 1            │                          │           SIDE 2
   the agent            │      Aito instance       │        the human
   (Claude)             │  contacts · touches ·    │       (operator)
        │                │      decisions           │            │
        │  MCP (stdio)   │                          │   HTTP      │
        ▼                │  ranking · $p · _relate  │             ▼
  company-ai MCP  ──────▶│  _recommend · learning   │◀──────  Segment 360
  server (7 tools)       │                          │         dashboard
   reasons & writes      └──────────────────────────┘        reads & shows
                                     ▲
                                     │  loaders (CLI)
                              rolodex + outcomes
```

Both sides query the *same* tables. An outcome the agent logs sharpens the
next brief **and** the next dashboard slice. Neither side holds logic of
its own: reasoning lives in Claude, statistics live in Aito, and these two
surfaces only compose and render what Aito returns.

---

## Shared setup (do once)

```sh
docker run -d -p 9005:9005 -e AITO_DISABLE_AUTH=true ghcr.io/aitohq/aito   # 1. the Aito instance
cp .env.example .env                              # 2. point at it (AITO_INSTANCE_URL)
uv run company-ai create-schema                   # 3. the tables
uv run company-ai load-rolodex --seed             # 4. data (omit --seed for the
uv run company-ai load-touches --seed             #    real set via COMPANY_AI_DATA_DIR)
uv run company-ai load-sessions --seed            #    website funnel data
uv run company-ai load-posts --seed               #    distribution post log
```

After this, pick a side. Most days you use both: the agent to run the
morning call window, the dashboard to step back and examine a segment.

---

## Side 1 — The agent: Claude over MCP

The agent side is for *doing the round*: who to call now, what to open
with, what changed, and logging each result in a sentence.

### Register the MCP server

Claude Code:

```sh
claude mcp add aito-company-ai -- uv --directory "$PWD" run company-ai-mcp
```

Claude Desktop: put the same command in `claude_desktop_config.json` under
`mcpServers`. Restart the session; the tools appear automatically.

### The seven tools

| Tool | Aito op | What the agent asks |
|------|---------|---------------------|
| `who_to_call(window, top_n)` | `_predict` | rank today's queue by `$p` of a good outcome |
| `opener_context(contact_id)` | `_similarity` | evidence touches from similar contacts, to draft an opener |
| `what_changed()` | `_query` | yesterday's touches + follow-ups due within 72h |
| `log_touch(contact_id, channel, window, outcome, …)` | write | record a call/email result |
| `log_decision(decision_type, context, chosen, confidence, human_action, …)` | write | record when the operator overrode the queue |
| `segment_360(segment, tier, ai_lifecycle, source)` | `_predict`/`_relate`/`_recommend` | the dashboard's analysis, in the chat |
| `predict(table, where, predict_field)` | `_predict` | escape hatch for any ad-hoc question |

### The morning brief

Drive it with `prompts/morning-brief.md`. The session: calls
`what_changed`, then `who_to_call` for the current window, then
`opener_context` per queued contact, and emits a one-screen brief
(follow-ups first, then the call queue with each `$p` and a suggested
opener angle). Claude writes the openers; the statistics only retrieve.

A model-free rendering of the same three queries:

```sh
uv run company-ai brief --no-llm
```

### Closing the loop

After a call, log it in a sentence ("log Helmi, called at 0800, no
answer") or with the shorthand:

```sh
uv run company-ai log <contact_id> call 0800 no_answer
```

Every logged touch is immediately queryable — it reorders the next brief
and shifts the next dashboard rate. That round-trip is the product.

---

## Side 2 — The human: the Segment 360 dashboard

The human side is for *stepping back*: how is a segment really doing, what
drives it, and which lever moves it. Read-only — you examine here and act
through the agent side.

### Run it

```sh
uv run company-ai dashboard          # http://localhost:8770
```

### What you examine

Pick a slice from the selectors — **segment · tier · ai_lifecycle ·
source** (any or all; "All" for the whole pipeline). Each KPI is a card:

| KPI | reads | good means |
|-----|-------|-----------|
| Conversion | `good_outcome` | the touch ended in conversation / meeting / callback |
| Reach | `reached` | the contact responded at all |
| Meetings | `booked` | a meeting was booked |

### How to read one card

- **The rate** — Aito's `$p` of the good outcome for this slice. Weak on
  thin data, and shown weak; that is honest, not broken.
- **▸ why this rate** — the base rate times the lift of each fixed segment
  attribute, so you see *why* it differs from the population.
- **Root causes** — the fields that most drive the KPI *within this slice*
  (`_relate`), each as rate-**with** vs rate-**without**. Drawn only from
  things known *before* the call, so a cause is actionable.
- **Lever** — the one field (`window` or `channel`) whose values most
  raise the good outcome (`_recommend`), best highlighted. "Top moves it
  N×" is the ratio between the best and worst option.

Slices are shareable by URL, e.g. `/?segment=erp&tier=A`.

### Funnels

The dashboard's **Funnels** tab visualizes two predictive funnels: the
website/acquisition funnel (visitor → signup → trial → paid, over
`sessions`) and the sales funnel (contact → … → meeting). Each shows the
funnel shape, the biggest-drop leak, Aito's outlook for the
deepest stage, why the slice leaks, and the lever that moves it. Spec in
`docs/09-funnels.md`.

### Post scorer

The **Post scorer** tab (messaging formula) predicts whether a draft will
win on its channel and explains the lever to pull before posting —
LinkedIn=reach, HN=views, never upvotes. Spec in
`docs/10-messaging-formula.md`.

### The same analysis without the UI

`segment_360`, `funnel`, and `score_post` are also MCP tools, so the agent
can pull a slice into the brief ("how's accounting/A converting?", "where's
the website funnel leaking for paid_search?", "score this LinkedIn draft")
without opening a browser.

---

## Why two sides, not one

The agent is fast and conversational but ephemeral; the dashboard is
slower but lets a human *see the shape* of a segment and trust the
numbers. Same brain, two reading speeds. And because Aito has no training
step, the loop is closed for both at once: log an outcome on the agent
side, and the dashboard's next render is already sharper — no retrain, no
sync.
