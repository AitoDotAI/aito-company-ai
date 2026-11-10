# 36 · Web KPIs, acquisition and journeys

Status: spec, for review. Builds on docs/35 (web_sessions). Asked by Antti,
5.11.2026.

For any visitor outcome that matters (a look at pricing, the contact form,
a sign-in, a sandbox, a first query), we want to answer:

- what visitors saw before it;
- where they came from and how they were acquired;
- which of those carry a lift, with honest counts;
- the journey, event by event, read forward from the landing or backward
  from the KPI.

Every number comes from Aito (rule 2). Python builds rows, calls Aito and
formats.

## KPIs

A fixed table in code (`webanalytics.KPI_EVENTS`) maps real Amplitude event
names to a few preselected KPIs. Antti chose the set on 5.11.2026. The
names are those seen in the export, 6.10–5.11.2026:

| KPI | Events |
|---|---|
| `pricing_page` | aito.ai's `/pricing/` page, by host and path (`KPI_PAGES`). *Changed 10.11.2026 (Antti):* the pricing-estimator demo's `Page View: Demo - Pricing` and beta.aito.ai's `/pricing/` are not it |
| `contact_page` | `Page View: /contact-us/` |
| `login_page` | `Page View: Sign In` |
| `signup` | `Page View: Sign Up`, `Page View: /sign-up/`, `signup_clicked`, `signup_completed` |
| `sandbox` | `sandbox_created`, `Instance create`, `Instance ready` |
| `data_loaded` | `File upload`, `data_uploaded` |
| `first_query` | `Workbook query executed`, `playground_query_executed` |
| `api_keys` | `Get API keys` |

The console steps form a funnel, in this order: `login_page`, `signup`,
`sandbox`, `data_loaded`, `first_query`. A new event name the site starts
sending isn't guessed into a KPI. Each pull reports event names outside
`KPI_EVENTS` and `KNOWN_EVENT_TYPES` (the other product events seen
6.10–5.11.2026) as `new_event_types`, and the CLI prints them as a warning,
not a failure. Someone then adds each name to the KPI table or the known list.

## Any event, not only the KPIs

Each session row also carries `events`: a Text field (whitespace analyzer)
holding every event kind in the session, normalised to a token. Page views
become their page, so `Page View: /pricing/` is `page:/pricing/`. Product
events become their snake-cased name, so `Workbook query executed` is
`workbook_query_executed`.

So `_relate` can take any event as the target, not only the KPIs. Probed on
2.12.0 (5.11.2026):

- `{"relate": {"events": "sandbox_created"}}` (a bare token) returns the
  context drivers;
- `{"relate": {"$and": [{"events": {"$has": "sandbox_created"}}]}}` also
  returns the co-occurring events, as `{"events": {"$has": …}}` hits;
- a top-level `{"events": {"$has": …}}` is rejected (400). aito-core
  traced it: an object value in `relate` is read as v1's nested-entity form,
  in place since v2.8.1. So we use the `$and` form. Once aito-core's
  relate fix lands, the plain `$has` form works too, and the queries can
  move to it.
- The `$and` form lists the target itself among its relations: in the probe,
  `events $has sandbox_created` with lift 5.41 was the self-relation, not a
  driver (aito-core, 5.11). `relations.relate` drops the outcome's whole
  field, but that would also drop the co-occurring events here. So the
  events insight drops only the same field AND value as the target and keeps
  the field's other values. The phase-1 book asserts the self-relation is
  gone and another event remains. The bare `$has` form, once fixed, excludes
  it in the engine.
- **Don't depend on same-field co-occurrence from `_relate`.** aito-core's
  relate fix makes the `$and` form exclude every field it names. On a
  multi-valued `events` field, that likely drops every other event value too,
  not only the self-relation. aito-core is checking, and a semantics ticket for
  Antti may follow. So co-occurrence never comes from the field the condition
  names:
  - For the preselected KPIs: relate against the `kpi_*` Boolean columns,
    which are separate fields, so the other KPIs come back as relations
    whatever the engine decides.
  - For any event: each session row also carries `co_events`, a second Text
    field with the same tokens as `events`. The condition names `events`, and
    the co-occurring events are read from `co_events`, a field it doesn't
    name. The target's own token in `co_events` is dropped as the
    self-relation. The lifts stay Aito's, with no Python arithmetic.
  - Once Antti decides the semantics, this can be simplified, but it is
    correct under either outcome. The CPO has asked aito-core to make the
    `$and` fix exclude only the named (field, value) self-relation and keep
    same-field co-occurrence. Once that ships, drop `co_events` and relate
    on `events` directly, to keep the schema lean.

## Tables

### web_sessions: new columns

| Field | Type | Meaning |
|---|---|---|
| events | Text, whitespace | every event token in the session, in order: a page view is `page:<page>` (redacted like `pages`), any other event its name snake-cased to `[a-z0-9_]`, never a property value; Amplitude's session_start/session_end are left out |
| co_events | Text, whitespace | the same tokens, for co-occurrence relations (see above) |
| kpi_pricing_page … kpi_api_keys | Boolean | one per KPI: the session had one of its events |
| visitor_key | String | HMAC-SHA256(salt, device_id), see Privacy |

`pages` (docs/35) stays as it is. `events` is its superset across event
kinds.

### web_visitors (new)

One row per visitor_key: the acquisition view across sessions.

| Field | Type | Meaning |
|---|---|---|
| visitor_key | String | as above |
| first_day, last_day | String | first and last session day |
| sessions | Int | sessions seen |
| first_source, first_referrer_domain, first_utm_source, first_utm_medium, first_utm_campaign, first_landing_path, first_device_class, first_country | String | the first session's context (first touch) |
| first_post_id | String, nullable, link to posts | the first session's exact post link |
| seen_before_first_kpi | Text | event tokens from the visitor's sessions before the first session with any KPI |
| kpi_* | Boolean | the visitor reached the KPI in any session |
| first_kpi_day_* | String, nullable | when |

It's rebuilt from the human web_sessions (bots left out) at the end of each
pull, under the same lock, with the same replace-by-run pattern (docs/35). The
pull report ends with a `web_visitors` line, and a failed rebuild is a health
problem like a failed day. `first_*` is the first session by (day, hour), and
`seen_before_first_kpi` holds the distinct tokens of the sessions before the
first one with any KPI (all of them, for a visitor who never reached one). Identity is per browser: one person's visits join only
within one browser, and that is deliberate (Antti, 6.11.2026). People do
different things in different browsers, such as reading docs in one and using
the console in another, so joining them would mix two journeys into one.

## Queries (all Aito)

- **Drivers of a KPI or any event**, over sessions or visitors:
  `_relate {"$and": [<target>]}` with the filters in `where`. Context fields
  only (the PRE_VISIT allow-list), plus `events` for co-occurring events.
  The KPI itself and the post-visit fields are excluded as leaks (relations.LEAKS).
- **Acquisition of KPI reachers:** on web_visitors, `_relate
  {"kpi_sandbox": true}` over the `first_*` fields and
  `seen_before_first_kpi`.
- **Rate for a filter:** `_query … limit 0` counts, sent in one `_batch`, for
  the KPI widget numbers and each filter row.
- **Trend:** the counts per week for the chosen KPI and filter (one
  `_batch`).
- **Journeys:** `_query` the sessions with the KPI, ordered by day, hour.
  The rows' `events` and `pages` are the journey. Backward means the
  visitor's earlier sessions (web_sessions where visitor_key = …, before the
  KPI day).

## Evidence, shown with every lift

Lifts on rare outcomes are unstable: a zero-count option gives a huge lift
(PR #32). Each insight row shows the counts behind it: rows with the value
and the target, and rows with the value. A row whose target count is under 5
is shown as "thin", with no bare lift number. The threshold is 5 (Antti,
6.11.2026; `webanalytics.WEB_THIN`).

## Dashboard: Web view

The layout follows the e-commerce demo's Analytics page
(aito-ecommerce-demo `app/customers/page.tsx`):

- **Left (sticky):**
  - a KPI widget: a grid of the KPIs, each with its rate for the current
    filter;
  - under it, the filters: source, utm_campaign / post, landing, device,
    country, and a date range. Each filter row shows the chosen KPI's rate
    for that slice, with a bar. Empty slices are greyed out.
- **Right:**
  - the trend: the chosen KPI per week, for the filter (solid) against
    everyone (dashed);
  - the insights, in tabs:
    - *Drivers*: `_relate` context lifts, with counts;
    - *Other events*: co-occurring event lifts, with counts;
    - *Acquisition*: first-touch lifts on web_visitors;
    - *Journeys*: the latest sessions that reached the KPI, with their
      event sequence.
- **Bottom:** the sessions matching the filter. 25 a page, with these
  columns: day, hour, landing, source, referrer domain, utm_campaign, post,
  device, country, views, events. It follows the same filter.
- State lives in the URL (kpi, filters, tab, date range), and a slow older
  response never overwrites a newer one.

MCP: `web_kpis(kpi | event, since, until, filters)` (built in phase 1) returns
the session counts, the pre-visit drivers, the other KPIs and the other events
(from `co_events`), so an agent and the view see the same answer. Relating
one console-funnel step drops the others as definitionally linked and names
them (`dropped_as_linked`). The target's own events are dropped from other
events. For an event target, the count matches the token with `$has` while
`_relate` takes the bare token, and the two counts must agree or it raises.
Phase 2 adds `acquisition` and `journeys`:
- `acquisition` (KPI targets): `_relate` over all stored web_visitors (lifetime,
  not the window) of first touch and `seen_before_first_kpi`, with counts and
  the thin flag. An event target has no visitor-level flag, so it is None.
- `journeys`: the latest 5 sessions with the target, each with its browser's
  earlier sessions (up to 10), oldest first, labelled "visitor N". The
  visitor_key never appears in a journey.
- **Journeys are internal only.** They are individual browsing histories,
  pseudonymous or not. `/api/web/kpi` replaces them with `[]` and sets
  `journeys_hidden` when the app serves a public demo (docs/33), and the Web
  view doesn't offer the tab there (book `test_journeys_never_reach_a_public_demo`).

Phase 3 (built): the Web view's KPI widget lists the 8 KPIs with their
session counts for the filter (`web_view` bundle `kpis`, plus per-day
`kpi_*` counts for the trend). Picking one shows its trend and, from
`/api/web/kpi` (the same `web_kpis` as MCP), tabs for drivers, other KPIs,
other events, acquisition and journeys, with the console-funnel steps left out
named above them, and each relation's counts or "thin".

## Privacy

Sign-in and sign-up events are where personal data appears. On 1–5.11,
`user_properties` held `email` and `fullName` on 36 events, and `user_id` was
set on 230.

- Never stored: `user_id`, `user_properties`, `ip_address`, `city`, `dma`.
  The pull keeps never reading `user_properties`. A book asserts that no
  email-shaped value lands in any row of web_sessions or web_visitors.
- Event tokens come from event *names*, never from event property values
  (`databaseName`, `id`, `basket_size` and the like are dropped). Page tokens
  are redacted like paths today (docs/35).
- **visitor_key and session_key are pseudonymous personal data.** Both are
  HMAC-SHA256 with a secret salt, `COMPANY_AI_WEB_SALT`, which Antti places
  in the env file. Without the salt, anyone holding the Amplitude export
  could recompute them. With it they can't be recomputed elsewhere, but here
  they still identify a browser. The salt was placed on 6.11.2026.
  web_sessions.session_key and visitor_key are salted (phase 1, first PR), and
  the backfill is re-pulled so that no unsalted key stays stored.
- Decided by Antti, 6.11.2026:
  - **No account linking.** Journeys stay per browser, and there is no
    account key. `user_id` is never read or stored.
  - **Delete on request.** By visitor key: `delete_entries` in web_sessions
    and web_visitors, plus a suppression list (salted visitor keys) so later
    pulls skip that browser. The operator triggers it with
    `company-ai forget-web-visitor --device-id <Amplitude device_id>` (or
    `--visitor-key`), or the local MCP tool `forget_web_visitor`, which is in
    REMOTE_DENY. Built in phase 2: the `web_suppressed` table, and
    `store_day` reports `suppressed` per day. The suppression list itself
    holds the pseudonymous visitor_key, as it must to suppress. A forget
    request needs the device id or key, which the operator gets from the
    person's browser (Amplitude's device id in its local storage, or the
    person sending it); it is never looked up from an email.
  - **Retention: 13 months.** At the end of each run the pull deletes the
    days before `retention_cutoff(today)` (13 calendar months back, clamped to
    the month end), checks none remain, and reports `retention`. A v2 delete
    takes equality only, so each old day is deleted by its own value.
  - **Backups expire on their own schedule.** Deletion and retention act on
    the live tables. Backups hold whatever was live when they were taken, and
    age out by rotation (docs/21): daily env snapshots after 7 days, tx
    snapshots after 16 newer tx ones, off-box CSVs after 90 days (the
    storage lifecycle rule). So a deleted visitor, or the unsalted
    session_keys before the 6.11.2026 re-pull (tx-1793943346), disappear from
    the backups within that time, not at once.
  - **Thin threshold: 5** (see Evidence).
- Still needed from Antti: the salt, `COMPANY_AI_WEB_SALT`, in the env
  file. Phase 1 starts once it's there.

## Phases

1. Salted keys (re-pull), the KPI table and the `events` field on
   web_sessions, `new_event_types` in the pull report, MCP `web_kpis` over
   sessions. The books come first: a fixture day with each KPI event; the
   salted key changes with the salt and never equals the bare hash; an
   email in user_properties never lands.
2. web_visitors, acquisition and journeys (backward from a KPI).
3. The dashboard Web view.

## Out of scope

Cross-device identity without sign-in, attribution models beyond first
touch and exact post links, and anything that writes back to Amplitude.
