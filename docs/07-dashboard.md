# The Segment 360 dashboard

A read-only web dashboard modelled on the Company 360 dashboard in
`aito-agent-demo`, applied to this repo's sales pipeline. It matters: a
human operator reads a slice far faster from KPI cards than from a query
log, and the cards are the system's clearest visual when showing it off.

> **Design principle.** The dashboard is a *view*, never a second place
> where logic lives. It runs no reasoning (that is Claude's) and computes
> no statistics (those are Aito's `_predict`/`_relate`/`_recommend`); the
> server only forwards query results to a page. Read-only reporting
> surfaces like this are in scope (CLAUDE.md rule 1); what stays out is
> anything that reasons or acts outside Claude and Aito.

## What it shows

Pick a segment slice (segment · tier · ai_lifecycle · source) and each KPI
is rendered as a card with the same anatomy as the demo: the **rate**, a
`why` expander, the **root causes**, and the **lever** that moves it.

| KPI | target (derived boolean) | good when | lever |
|-----|--------------------------|-----------|-------|
| Conversion | `good_outcome` | outcome ∈ conversation/meeting/callback | `window` |
| Reach | `reached` | the contact responded at all | `channel` |
| Meetings | `booked` | a meeting was booked | `channel` |

The three KPI booleans are deterministic relabelings of `outcome`,
derived at load/log time (`schema.kpi_flags`), so Aito can `_predict` a
clean `$p` and `$why` per KPI. They are data prep, not inference.

## Three Aito calls per KPI

Exactly the demo's pattern (`analytics.py`):

1. **Rate + `$why`** — `_predict` the boolean for the slice; the rate is
   `$p(true)`, the `$why` is its base-rate × per-condition lifts.
2. **Root causes** — `_relate {$on: [ {target: true}, segment ]}`: the
   fields that drive the KPI *within this slice*, ranked by Aito's mutual
   information, shown as rate-with vs rate-without. Causes are drawn from
   an allowlist of fields known *before* the call (contact attributes and
   the touch's window/weekday/channel/recency); `outcome`, `next_action`,
   and `notes` are excluded as leakage.
3. **Lever** — `_recommend {goal: {target: true}}`: which value of the
   lever field most raises the good outcome for the slice, each with `$p`.

Python assembles the request bodies and orders Aito's own returned
statistics; it computes no rate, cause, or lever itself.

## Running it

```sh
uv run company-ai dashboard          # http://localhost:8770
```

Standard-library HTTP server, zero new dependencies. Serves one static
page (`static/dashboard.html`) and a `GET /api/360` JSON endpoint. Slices
are shareable via URL, e.g. `/?segment=erp&tier=A`.

The same analysis is available without the UI as the `segment_360` MCP
tool, so a Claude session can ask for it in the brief flow.

## Tested

`book/test_analytics.py` snapshots the rates, causes, and levers on both
seed datasets plus the cold-start tiny set. The HTML is the only surface
not under booktest — it carries no logic, so the snapshotted data layer
is where correctness is checked.
