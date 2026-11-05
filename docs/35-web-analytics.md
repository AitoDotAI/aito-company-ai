# Web analytics: aito.ai traffic in the Company AI

Status: design, 5.11.2026 (td-20261105085533404594). Antti 5.11.2026: "we
should try our own dogfood. As a part of that effort, we should bring some web
analytics to our company ai".

The site (aito.ai) already sends page views to Amplitude, project "Aito.ai"
(appId 100040781, EU data centre, UTC, 30-minute sessions). The Company AI has
posts, experiments and engagement KPIs, but no web traffic, so the effect of a
distribution drop is read off Amplitude by hand. This brings the traffic in as
an Aito table that the tools and Aito's queries can use.

## Session rows, not daily rows

One row per Amplitude session, in a new `web_sessions` collection.

- **Aito predicts over rows.** "Which source + landing page leads to an onward
  click" is a `_predict` / `_relate` over sessions with an `onward_click`
  Boolean. A daily row holds counts (12 sessions, 3 onward clicks), and Aito
  cannot condition a probability on a count. The dogfood question needs the
  session grain.
- **Daily numbers come out of rows.** `web_traffic` builds the per-day view
  from a projected read of the rows, tallied by day (counting is formatting, not prediction; `_aggregate` groupBy was ignored when measured on 2.11.1), so no second table is
  needed and the two can never disagree.
- **The size is small.** About 750 front-page views in the last 30 days, so a
  few thousand session rows a year.

The existing `sessions` table (the website funnel, docs/09) stays as it is.
Its stage flags (signed_up, started_trial, converted_paid) depend on account
events that Amplitude does not tie to the web session reliably. Its seed
carries a planted signal the funnel books depend on. Feeding the funnel from
`web_sessions` is a later step, once the flags have a source.

## Fields

| field | type | from |
|---|---|---|
| session_key | String | sha256 of Amplitude session_id + device_id, first 16 hex characters. Stable, so a re-pull replaces the same row. One key per session: the same visitor's next session gets an unrelated key, so rows are not linkable across sessions. Still pseudonymous, not anonymous: someone holding the raw Amplitude data could recompute it. |
| day | String (YYYY-MM-DD) | UTC date of the session's first event; hour, weekday and week are of the same event |
| hour | Int | 0-23 UTC |
| weekday | String | derived from day |
| week | String (YYYY-Www) | ISO week of day: the grain of the weekly rollups |
| landing_path | String | path of the first page view, query string and fragment dropped, an email-shaped segment as `<email>` and a token-like one (16+ hex, or 24+ characters without hyphens) as `<token>`. A page on another host (a demo such as ecommerce.aito.ai) is written host-first: `ecommerce.aito.ai/cart`; aito.ai pages are the bare path. |
| next_path | String, nullable | the second page viewed, written like landing_path; null when the session ended on its landing page |
| pages | Text | the paths viewed, in event-time order, space-joined, repeats kept (lets text match find "visited /pricing"; the order is the visit's) |
| views | Int | page views in the session |
| engaged_seconds | Int | last event minus first event |
| onward_click | Boolean | the session went past its landing page: a second page view, or a CTA/sign-up event |
| signup_cta | Boolean | a sign-up CTA or sign-up page was reached |
| referrer_domain | String, nullable | the referrer's host, `www.` dropped; null when direct |
| source | String | organic, social, referral, direct, paid, email, or other. Classified from utm_medium first, then referrer_domain, by a fixed table in code. This is a label lookup, not a heuristic score. |
| utm_source, utm_medium, utm_campaign | String, nullable | from the landing URL's query string (`[Amplitude] Page URL`, else `Page Location`), lowercased, spaces as `_`; a value that isn't a short plain slug (up to 64 of a-z 0-9 . _ -, no hex token) is stored as `<invalid>` and counted |
| device_class | String | desktop, mobile, tablet, or unknown, from os_name by a fixed table. Each pull reports how many sessions came out unknown, and the OS names behind them. |
| country | String | Amplitude's country |
| likely_bot | Boolean | the landing path is a known probe (/admin, /wp-login.php, dotfile probes, /airdrops, …; a fixed prefix list). Flagged, never dropped (rule 3). A one-page session is NOT flagged: that is an ordinary bounce. |
| post_id | String, nullable, link to posts | the exact link: utm_campaign is that post's slug, and the visit is on or after the day it went out |
| candidate_post_id | String, nullable, link to posts | the referrer_day candidate, kept apart from post_id so exact and guessed links never mix in a query |
| experiment_id | String, nullable, link to experiments | utm_campaign equals an experiment_id |
| link_basis | String, nullable | utm_campaign or referrer_day: how the link was made |
| pull_run | String | the pull that wrote the row: a re-pull uploads under a new run, checks it, then deletes the old run's rows |

## Privacy

The Export API returns raw events: user_id, device_id, IP address, full URLs
with query strings, and user properties. None of that is kept.

- **Never on disk.** The export is read into memory, unzipped and parsed
  there. No raw file is written, not even to a temp directory.
- **Allow-list, not a block-list.** A stored row is built field by field from
  the table above. Anything not named there (ip_address, user_id, device_id,
  user_properties, the full URL) is never copied. Paths are cut at `?` and
  `#`; the three utm values are the only part of a query string kept.
- **Redaction.** A path segment that holds an email-shaped string becomes
  `<email>`; one that holds a token (16+ hex characters, or 24+ characters
  without hyphens, so a long blog slug survives) becomes `<token>`. utm
  values are charset-limited (see Fields).
- **A gate that can fail.** The book scans every field of every stored row
  for the fixture's IPs, device ids and user ids, for `?`, `=` and `utm_`
  inside paths, for any `@`, and for long tokens outside the generated id
  fields. It runs again with the path scrubber and the key hash
  stubbed out, and again with the segment redaction stubbed out, and each
  time must report the leaks. That shows the check is live.
- Real rows live only in the internal Aito; the repo ships a synthetic
  fixture (rule 6).

## Landing → next path

The front-page block (td-20261105085533734697) needs to know which page
people went on to from each landing page, by source and device. That comes
from the same session rows, through `next_path`; there is no separate counts
table.

- **Counts.** `web_paths(since, until, landing_path, source, device_class)`
  counts sessions by landing_path, next_path, source and device_class, from
  a projected read of the rows. The default grain is weekly (`week`), because at ~450-650
  sessions a week the per-path counts by day are mostly zeros and ones. Any
  range can be asked for, since the rollup happens at read time over rows
  that are already stored, so nothing has to be rebuilt.
- **The prediction.** `_predict next_path` with landing_path, source and
  device_class as conditions is the front-page recommendation itself:
  P(next page | how the visitor arrived), with `$why`. It is the same table
  and the same privacy rules, and a stronger dogfood than counts alone. Thin
  data shows as low `$p` (honest-weak); counts stay beside it.
- Bots are excluded from both by default.

## Clicks into the demo subdomains

The demos (ecommerce.aito.ai and others) send to the same Amplitude project.
Whether a click from aito.ai into a demo stays one session depends on the
browser SDK sharing its device_id cookie across `.aito.ai`.

- **Shared:** the demo page view arrives with the same session_id and
  device_id. It lands in the same session row as a host-first path
  (`ecommerce.aito.ai/…`), so it counts in onward_click, next_path and
  pages.
- **Not shared:** the demo visit is a separate session, with its own landing
  page and referrer aito.ai. The aito.ai session then shows the click only if
  the site sends a click event before leaving. Today no such outbound event
  exists in the taxonomy (only demo_signup_cta_clicked). So the click counts
  in neither onward_click nor next_path; it shows as a referral session on
  the demo's side (referrer_domain = aito.ai).

Which case holds can't be seen from the taxonomy. The first real pull
reports how many sessions span two hosts, and how many demo sessions have
referrer aito.ai. If it's the second case, the fix is on the site: share the
cookie domain, or send an outbound-click event. That's a ticket for the
website lane, not a workaround here.

## Linking to posts and experiments

1. **utm_campaign = the post's slug.** This is exact, and fills `post_id`. Each post stores a
   readable `utm_campaign` (posts.utm_campaign, set with `add_post`, unique
   when set), and its links carry it: `?utm_source=linkedin&utm_medium=social
   &utm_campaign=ecom-screen`. The convention was agreed with the CRO session
   on 5.11.2026:
   - a short slug, with a channel suffix only when one material ships as
     several posts on the same platform (`ecom-screen-co`);
   - utm_source and utm_medium as before (linkedin/social, reddit/social,
     newsletter/email);
   - an experiment's drop sets its post's slug to the experiment_id, so the
     session links to both the post and the experiment; a campaign equal to
     an experiment_id with no post links the experiment alone;
   - Hacker News links go out clean, with no UTM, so HN visits stay on the
     candidate rule below; LinkedIn reshares carry no new link and show as
     linkedin referrer traffic.
2. **Otherwise, referrer_day.** The referrer's platform matches exactly one
   post posted on that platform within the 3 days before the session (for
   example news.ycombinator.com → the one HN post that week). It fills
   `candidate_post_id`, never `post_id`, and `link_basis = referrer_day`; the
   tools list candidates apart. With zero or several posts matching, nothing
   is linked.
3. **Never credited:** a visit dated before the post went out (counted as
   `before_post`), and a slug that two posts share. add_post refuses a
   duplicate, but that check is not atomic, so the pull reports any
   duplicate in `duplicate_campaigns` and links neither post.

`log_experiment_result` is not changed. `web_traffic(campaign=<id>)` returns
the numbers to pre-fill it: sessions, onward clicks, sign-up CTAs.

## The pull

- `company-ai pull-web [--day YYYY-MM-DD] [--days N]` calls Amplitude's
  Export API (`https://analytics.eu.amplitude.com/api/2/export`, one UTC day
  per call, a zip of gzipped JSON lines). It groups the page views into
  sessions and replaces that day's rows. The new rows are uploaded under a
  fresh `pull_run` and counted. Only then are the earlier runs' rows for the
  day deleted, so a failed upload leaves the day as it was. Re-running a day
  gives the same rows. A day that comes back with no sessions keeps what it
  had and is flagged `empty`.
- **A session belongs to the day of its first event.** Pulling day D reads
  the Export API from D-1 00h to D+1 23h and keeps the sessions whose first
  event is on D. A visit from 23:58 to 00:01 is one row on its first day,
  and the morning half never shows up as a fake landing on the next day. The
  Export API may select by upload time rather than event time, which the
  wide window also covers; check it on the first real day.
- **Each day is stored on its own.** A day that fails is reported with its
  error, the other days still run, and the command exits non-zero at the
  end.
- **Counted, never fatal:** a page-view event with no path (`Viewed (no
  path)` in `unmapped`), unknown OSes, and events with Amplitude's "no
  session" id (-1). Each of those events becomes its own one-event
  session, so a device's whole day is never merged into one, and is counted
  in `no_session_events`.
- **Silent nulls show up.** Each run counts sessions with a utm value
  (`utm_present`) and with a referrer (`referrer_present`). In the real
  Browser SDK these may sit elsewhere than the fixture assumes (user
  properties, or Page Location instead of Page URL). Zeros on a real day mean
  the parser is looking in the wrong place.
- **Page views have two shapes**, and both are mapped: `Page View: /path`
  (one event type per path, 918 of them) and `Viewed …` (titled views with a
  path property). Each run reports how many events it mapped per shape, and
  how many other events it saw and did not map, by type. A `*_cta_clicked`
  event counts towards onward_click and signup_cta. Consolidating the site to
  one page-view event with a path property is a website-lane ticket; the
  parser keeps working on both shapes.
- The key is `AMPLITUDE_API_KEY` + `AMPLITUDE_SECRET_KEY` in `.env.aito`.
  Antti places them himself; no agent creates, reads or relays them. Without
  them the command fails loudly.
- It runs daily from an OS timer (`ops/systemd/company-ai-web-pull.timer`,
  04:30 local time), the same shape as the compaction timer. There is no
  in-app scheduler (rule 1). It is a systemd user timer on Antti's
  workstation, the machine that already runs the compaction timers against
  internal; it is not on the Azure app. Each run pulls the last 3 UTC days
  (`--days 3`), so a day missed because the machine was off is backfilled by
  the next run. Since a re-pull replaces a day, the overlap costs nothing. A
  gap longer than 3 days needs `--day` by hand, and the run reports the
  newest day already stored so a gap shows. Installing the timer is a local
  change: the unit file goes to review first.
- An event the pull does not recognise is counted and reported per run, never
  silently skipped (rule 3).

## Reads

- MCP `web_traffic(since, until, path, campaign, source)`: per-day sessions,
  views, onward clicks and sign-up CTAs, the top landing
  pages and sources, and the linked post or experiment. Bots are excluded by
  default and counted separately.
- The weekly KPIs (`engagement_kpis`, docs/34) get `web_sessions` and
  `web_onward_click_rate` per ISO week, bots excluded; a rate over no
  sessions is null. On an instance without the table yet, both are null and
  `web` carries a note, rather than the KPIs failing.

## The dogfood query

`_relate` over `web_sessions` (bots excluded, in the asked window and
landing path) on `onward_click: true`. The drivers are only the context a
visitor arrives with: source, referrer_domain, utm_source, utm_medium,
utm_campaign, landing_path, device_class, country, weekday and hour. What
happens during the visit (next_path, views, signup_cta, engaged_seconds)
defines the click, so `relations.LEAKS` excludes it, and bookkeeping
(session_key, day, week, pull_run, link fields, likely_bot) is never a
driver. It
answers "which source and landing page produce onward clicks". `_predict
onward_click` given a planned post's platform and landing page gives a
before-posting estimate, next to `score_post`. Both are Aito queries; Python
only formats them (rule 2).

## Gate

A synthetic Amplitude export fixture (`data/fixtures/amplitude_export_*.jsonl`,
invented events) goes through the real parser into a test env. The book
asserts the stored values: a 3-view session from a utm-tagged LinkedIn link
lands with views=3, onward_click=true and post_id set; a single bot probe lands
with likely_bot=true; a re-pull leaves the row count and values unchanged. It
must fail before the parser exists.

## Out of scope

Replacing Amplitude or GA4 on the site; consent changes; GA4 as a second
source; feeding the docs/09 funnel.
