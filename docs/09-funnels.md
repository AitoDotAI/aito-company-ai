# Funnels

Two predictive funnels over the same Aito instance. A funnel here is not a
bar chart of counts — it answers the founder's question: **where is this
slice leaking, what's the outlook, and which lever moves it.**

| Funnel | Table | Stages | Marketing dimension |
|--------|-------|--------|---------------------|
| Website / acquisition | `sessions` | visitor → signed up → started trial → paid | `source`, `campaign` |
| Sales | `contacts` | contact → touched → reached → conversation → meeting | `source` |

## What each funnel reports

For any slice, all of it from Aito (`funnels.py`):

1. **Stages + step conversion** — `_query` totals per stage; the page
   divides counts into percentages (formatting, not inference). This is
   the funnel shape.
2. **The leak** — the step with the lowest continue-rate, flagged.
3. **The outlook** — `_predict` of the deepest stage for the slice, with
   `$why` (base rate × the lift of each fixed dimension). This is Aito's
   smoothed probability, which on a thin slice differs from the raw
   count-rate — and that difference is the honest part.
4. **Why it leaks** — `_relate {$on: [deepest_stage, slice]}`: the
   pre-event attributes that drive reaching the deepest stage *within this
   slice*, as rate-with vs rate-without. Causes come from an allowlist of
   fields known before the event (no leakage from the stage flags).
5. **The lever** — `_recommend {goal: deepest_stage}`: which value of the
   lever field most raises conversion. Website lever is `source` (where to
   put acquisition spend); the sales funnel has no single controllable
   lever on the contact master, so it shows none.

Python assembles the requests and orders Aito's own returned numbers; no
rate, cause, or lever is computed here.

## The data

- **`sessions`** — one row per website visit, with monotone stage booleans
  (`signed_up` → `started_trial` → `converted_paid`) and the dimensions
  `source` / `campaign` / `landing_page` / `country` / `device`. Loaded by
  `company-ai load-sessions` (`--seed` for synthetic; real data via
  `COMPANY_AI_DATA_DIR/sessions.csv`).
- **Sales stages** — derived onto `contacts` at load time from touch
  history (`ever_touched` … `ever_meeting`, monotone). These are a
  load-time snapshot: touches logged afterwards do not retro-update them,
  so rerun `load-rolodex` to refresh the sales funnel. The website funnel
  has no such lag (sessions carry their own flags).

## Using it

```sh
uv run company-ai load-sessions --seed
uv run company-ai dashboard            # http://localhost:8770/funnels
```

Pick a funnel and a slice; the page shows the funnel chart on the left and
the Aito read (outlook, leak causes, lever) on the right. Slices are
shareable by URL, e.g. `/funnels?name=website&device=mobile` — which
surfaces the planted signal that mobile sessions drop hardest at the
signup→trial step.

The same analysis is the `funnel(name, slice)` MCP tool, so a Claude
session can ask "where's the website funnel leaking for paid_search?"
without a browser.

## Not modelled yet

Ad spend, impressions, and clicks — so cost-per-acquisition and ROAS are
out of scope until a `campaigns` table with spend lands. The funnel shows
conversion and the best channel by conversion, not yet by cost.
