# The dashboard app (React + FastAPI)

The human side of the system is a **React app over a FastAPI backend**. The
backend is the JSON contract; the React app and the agent are two faces over
it (`docs/08-two-sides.md`).

```
   React app  ──fetch /api/*──▶  FastAPI (api.py)  ──▶  analytics / funnels /
   (frontend/)                        │                  scorer  ──▶  Aito
                                      │
   Claude agent  ──MCP tools──▶  server.py  ───────▶  (same functions)
```

Both the UI and the agent call the **same data layer** (`analytics.py`,
`funnels.py`, `scorer.py`). Neither the FastAPI routes nor the React
components compute anything predictive — the API returns each function's
`.derived` payload verbatim, so the data-layer booktests already pin the API
shape. The UI renders; the intuition stays in Aito.

## Why this shape

A standalone React app (not a Claude artifact) gives a rich, lasting human UI
while keeping the agent path untouched: the agent never renders pixels, it
reads the data layer over MCP. The framework choice is therefore a
human-UI decision, not an agent one — see `docs/08` for the reasoning. The
cost accepted: a Node/build toolchain, and the UI sits outside the booktest
discipline (the data layer stays fully tested).

## Backend (`src/company_ai/api.py`)

FastAPI. Read-only `/api/*` endpoints, each a thin wrapper over the data
layer, errors surfaced as `{"error": ...}` rather than blank panels:

| route | returns |
|---|---|
| `/api/dimensions` | Segment 360 slice dimensions + values |
| `/api/360` | `segment_360(slice)` |
| `/api/funnels` | the funnel catalogue + per-funnel dimension values |
| `/api/funnel?name=&…` | `funnel(name, slice)` |
| `/api/score-options` | post scorer feature list + value options |
| `/api/score?channel=&…` | `score(channel, features)` |
| `/api/docs` | auto-generated OpenAPI docs |

It also serves the built React app (SPA fallback) from `web_dist`.
`company-ai dashboard` runs it via uvicorn.

## Frontend (`frontend/`)

Vite + React. The information architecture follows rev 3 of the
architecture spec: a fixed left nav — **Now · Work (Sales, Distribution,
Operations, R&D) · Knowledge · Analytics** — and every view is composed from
shared **primitives** (`kpi-row`, `chart`, `optimizer`, plus the
action/document primitives still to come). A view is an ordered list of
blocks; `views.jsx` holds the built-in views, `primitives.jsx` the building
blocks, `api.js` the fetch helpers.

**What is live vs. pending.** Live: the action-first Now view and every Work
view's action block (over the `todos` table, `docs/12`); the analytics
surfaces — Analytics (Segment 360 + funnels) and Distribution (website funnel
+ post scorer); and the Knowledge **Documents** store (`document-store` over the
`documents` collection — kind/area filters, company/person links, an in-place
editor — served by `/api/documents`, rendered by a small in-house markdown
component; docs/25).
The **Data** view (under Analytics) is a raw spreadsheet over any table —
every row, unfiltered, including the old/closed cases the analytics views
leave out (`/api/tables`, `/api/table`, `sheets.py`). Where the funnel and
pipeline *derive and filter*, the sheet just shows the rows.

The `optimizer`, `kpi-row`, `chart`, `action-*`, `document-tree`, and
`sheet` primitives are all built; future views are compositions of them.

**View tabs.** A view can declare named `tabs` (each a labelled panel), and
`TabbedView` renders a tab strip — one thing per tab, which matters most on a
phone where several heavy blocks in one scroll is unusable. The **Sales** view
splits into **Pipeline** (deals + Aito close-likelihood) · **Companies** ·
**Calls** (this week) · **Funnel**. When a view exposes raw-row `data` specs a
**Data** tab is appended automatically; a view with a single panel shows no
strip. **Companies** is the rollup of contacts by company joined to their deals
(`companies.py`, `/api/companies`, MCP `company_list`) — there is no accounts
table, so `company` is a string and this is the read surface that treats it as
one: contact count, furthest funnel stage, and open pipeline per company.

## Building and running

```sh
cd frontend && npm install && npm run build && cd ..
uv run company-ai dashboard          # http://localhost:8770
```

`web_dist/` (the build output) and `node_modules/` are gitignored; a fresh
clone runs `npm run build` once. During UI work, `npm run dev` (Vite on
`:5173`, proxying `/api` to the backend) gives hot reload.

## Testing posture

The data layer (`analytics`/`funnels`/`scorer`) is booktested, so the numbers
the API serves are pinned. The FastAPI routes are thin pass-throughs and the
React components carry no logic, so they are verified by eye, not snapshot —
the deliberate trade in adopting a UI framework here.
