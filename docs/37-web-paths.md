# 37 · Paths through the web data, as a graph

Status: design approved (CPO, 6.11.2026); phase 1 (`web_steps`) built. Asked by Antti, 6.11.2026:
"those graph db functionalities are going to be useful with the new web
analytics data and journeys, e.g. we want to query paths from e.g. landing
page to a KPI", and "continue the paths from various distributions like
LinkedIn, Reddit or similar to web traffic and KPIs".

So the path runs: **post on a channel → visit → page … page → KPI.** Every
number stays in Aito (rule 2). Where Aito can't answer yet, the gap goes to
aito-core as a ticket rather than being computed in Python. The privacy
rules of docs/36 hold: per browser, pseudonymous, internal only. This is also
the first real customer of Aito's graph features, so it doubles as dogfood.

## What Aito's graph features can do today

From aito-core master (71ab402b3c, 6.11.2026). Sources: the capability matrix
book (`GraphCapabilityMatrixTest/graph-capability-matrix.md`),
`api-docs/content/graphs-v2.md`, and the roadmap
`ai/strategy/graph-minimum-set-2026-10-29.md`.

- **rep2 collections only.** Multi-hop forward paths (`prev.prev.page`),
  self-links (`prev: "this.step_id"`), and reverse `$refs.<table>.<fk>` with
  `$exists`/`$length` work on rep2 collections. rep1 tables allow one forward
  hop and no `$refs`. **A link can't cross the two engines.** All of this
  repo's tables are rep1 (`"type": "table"`), so the path data has to be a
  self-contained rep2 collection.
- **Works today on rep2:**
  - 2- and 3-hop forward paths, and self-links two hops deep;
  - `$refs … $exists: false` (no row points back here);
  - `_relate` over a link path (on both engines);
  - `relate {"$patterns": [...]}` over link paths: top itemsets of up to 6
    items, greedy, not exhaustive;
  - a first-order "next step" `_predict` through the self-link.
- **Not on master:**
  - path enumeration, shortest path and k-hop reachability: M5,
    `$walk`/`$reaches`, which is unowned;
  - operators such as `$gt` inside `$exists`: M4, on a branch, not merged;
  - `recommend` over a linked path, which returns a 500
    (td-20260926215842222183);
  - lazy `$refs`: M6, since `$refs` is built eagerly.
- **Speed:** 3-hop filters took 9–11 s on the sandbox. Our scale (thousands
  of steps a month) is small, but it's worth measuring.

## The graph model

Built at pull time from data already stored: `web_sessions.events` holds each
visit's ordered tokens (docs/36), and `post_id` holds the exact post link.

**`web_steps`** is a new **rep2 collection** with one row per event of a
visit, in order:

| Field | Meaning |
|---|---|
| step_id | `<session_key>:<n>` (pseudonymous, like session_key) |
| prev | self-link `this.step_id`: the step before (null on the landing step) |
| token | the event token: `page:/pricing/`, `sandbox_created`… (docs/36) |
| n | the position in the visit, 0 = landing |
| is_kpi | the token belongs to a KPI (`KPI_EVENTS`) |
| kpi | which KPI, or null |
| kpi_after | some later step of the same visit is the KPI being studied. One Boolean per KPI (`kpi_after_<k>`) |
| is_exit | the last step of the visit |
| source, utm_campaign, referrer_domain | the visit's arrival, copied onto each step |
| post_platform, post_id | the exact post link's platform (linkedin, reddit, hackernews…) and id, copied on |
| visitor_key, day | as on web_sessions; never relation drivers |

The arrival and post fields are copied onto each step because a link can't
reach the rep1 `web_sessions` or `posts`. The `kpi_after_*` flags and
`is_exit` are facts about the visit, worked out at ingest. They aren't
predictions: they're what lets Aito answer "later in the visit" today,
without M4.

## The queries Antti means

**1. Which channels and posts lead to a KPI.** This one is mostly answerable now:
- Over sessions: `_relate {"kpi_sandbox": true}` with the visit's
  `source`/`utm_campaign`/`referrer_domain`, as in `web_kpis` drivers today.
- Per platform: `post_platform` on `web_steps` (or a derived
  `post_platform` on `web_sessions`) makes LinkedIn vs Reddit vs HN a
  driver.

The real limit is coverage, not the engine. Only visits whose link carries
the post's `utm_campaign` link exactly. Referrer-day guesses stay
candidates. So every post needs its utm slug (the CRO's habit; docs/35).

**2. The most common paths from a landing page (or a channel) to a KPI, 2–4
steps.** A workaround today:
`from web_steps where {"kpi": "sandbox", "prev.prev.prev.token": "page:/"}
relate {"$patterns": ["prev.token", "prev.prev.token", "prev.prev.prev.token"]}`.
Each item is tied to a field, so the step position is kept. That gives Aito's
top patterns, not a full count, and only for fixed depths.

Gap 1 → aito-core: paths of any length, landing → KPI, top-k with counts.
That is M5's `$walk` over `prev`. It should not be counted in Python.

**3. Which pages raise the chance of reaching a KPI later in the visit.**
Answerable now:
`from web_steps where {"is_kpi": false} relate {"kpi_after_sandbox": true}`.
That gives the token drivers with lift and counts, through the thin flag as
everywhere. Per channel, add `"post_platform": "linkedin"` to the where.

Gap 2 → aito-core: without the ingest-time flag, this needs
`$refs.web_steps.prev` with `$exists: {"n": {"$gt": …}}` (M4).

**4. Drop-off: where visits end before the KPI.** Answerable now:
`from web_steps where {"is_exit": true, "kpi_after_sandbox": false}
relate {"token": …}`, or the `$refs.web_steps.prev $exists: false` form,
which needs no flag. Whether `_relate` accepts a `$refs` `where` is likely
but not verified, so the build's first book checks it. If it fails, that's
Gap 3 → aito-core.

**5. Next step.** Answerable now:
`from web_steps where {"prev.token": "page:/pricing/"} predict "token"`.
It's the first-order version of `web_paths`, and `$why` comes with it.

## Privacy

`web_steps` holds no more than web_sessions already does (the same tokens and
keys), split by step. Its rows are browsing histories, so they are internal
only, like journeys (docs/36). `forget_web_visitor` and the 13-month
retention extend to it by `visitor_key` and `day`. Paths are only ever shown
in aggregate (patterns, relations), and a single visit's path appears only in
the internal Journeys tab.

## Phases (after review)

1. `web_steps` (rep2), built in each pull, with replace-by-run per day,
   deletion and retention (built). Probed first on the test engine (2.12.0),
   on a scratch collection: 2-hop `prev.prev.token` filters, the `$refs`
   exit form, `_relate` with that `$refs` where (so gap 3 is not a gap),
   `$patterns` over the prev chain, and `_predict` of the next token all
   work. Gaps 1 and 2 already had aito-core tickets (td-20260927120713200883
   for `$walk`, td-20260926161012650280 for operators inside `$exists`), and
   our use case and queries were appended to them.
2. MCP `web_paths_to(kpi, since, until, platform)` and a Paths tab in the Web
   view's KPI insights (built). It returns top paths ($patterns, up to three
   steps back, with visits, lift and thin), the pages after which the KPI more
   often follows (`kpi_after_<kpi>` over the token) and drop-off (`is_exit`
   among visits that never reach it). Aggregates only.
3. File gaps 1–3 with aito-core, each with the exact request that fails or
   has to be worked around.

## The weekly digest (built 6.11.2026)

`web_digest(as_of)` (MCP `web_digest`) lists, for every KPI, the signals of
a rolling window before `as_of` that are **not thin**: `raises_later` and
`drop_off` rows of `web_paths_to` with lift > 1 and at least `WEB_THIN` (5)
distinct visits. The window is `DIGEST_WINDOW_DAYS`, 28 by default (env
`COMPANY_AI_WEB_DIGEST_DAYS`): at our volume a single week almost never gets
past thin. It's computed weekly, and a signal is `new` when last week's
digest (the same window, seven days earlier) did not show it. No threshold
beyond thin; Aito ranks and scores.

So these surface without anyone asking, `pull-web` on a Monday (UTC) saves
the digest as an internal document (area `marketing`, topics `web;digest`,
title `Web digest, <since>..<until>`). A re-run the same Monday finds the
same title and body and records nothing new. It runs with the daily
web-pull timer, so nothing extra is scheduled; installing that timer is the
operator's.
