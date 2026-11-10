# 44 · Web insights: what leads to a KPI, and what content does (spec for review)

Status: **spec, for review.** Asked by Antti, 10.11.2026. It builds on
docs/35 (web_sessions), docs/36 (KPIs, acquisition, journeys) and docs/37
(paths), and reworks the Web view along the lines of the e-commerce demo's
Analytics page. The questions come from Antti, from the CRO session's
answer (10.11.2026), and from the website session for the consultative
layer.

## The ask (Antti, 10.11.2026)

Two directions over the same data:

1. **KPI → what led to it.** For a KPI such as a sign-in: what goes with it,
   what visitors did and saw before it, where they came from, and which
   campaign or post it traces back to. In short, which marketing efforts
   connect to success.
2. **Content → its effect.** For something we can act on (a blog post, a
   page, a variant): did reading it lead to a sign-in? Which content makes
   people drop out? Do demos work?

## What the CRO would do with the answers

| Question | What it changes |
|---|---|
| Per post or campaign: the share of landed sessions that go onward (second page, pricing, docs, sign-up), not landings | which post to push in the Tuesday slot, which channel to retire |
| Per channel and source: onward and sign-up rate, warm vs cold | where outreach effort goes |
| What goes with sign-up or contact: landing vertical, pages before, demo seen, source | which vertical's accounts get the Sunday drafts |
| Demo opened vs not: sign-up and contact rate; the exit right after a demo | keep investing in demos; which demo to link in follow-ups |
| High-intent exits: reached pricing, trust or sign-up, then left. From where, after what | a page fix, not a call |
| Which vertical's landing is pulling, week over week | the next outreach vertical |
| The consultative needs: which interests, domain and stage go with contact or a sign-up click | the next guide or post |
| The questions the guide could not answer (`answer_source = none`, labels only) | the next post or guide answer. **Parked:** it lives in the beta's own table, not Amplitude, and waits for direct mode or a read path |
| A post's 7-day result: sessions, onward, sign-ups by utm | `log_post_result` without hand-work |

**Not built: per-person or per-company tracking** (the CRO's line, and
the consent setup and trust page). No IP-to-company lookup. Surfacing a
*known, signed-in* user from a rolodex account who visits pricing in
`who_to_call` is a separate proposal for Antti, parked here.

## Honest at small counts (the CRO's first condition)

In a month of real traffic, the high-intent KPIs (contact, sign-up) reach
only tens of sessions. At such counts most lifts are noise.

- Every relation shows **n** (sessions with the value, and of those how
  many reached the KPI) next to its lift. Under 5 it's listed greyed as
  "thin, no claim" (docs/36's existing `thin_below`, raised to 5).
- **Highlights rank by excess, n ≥ 5**: the KPI sessions observed with
  the value, minus those expected at the base rate (n with the value ×
  the base rate), positive only. Plain arithmetic on counts. Neither lift
  alone (a 2-of-2 tops it) nor count × lift works: a page seen in 500
  sessions at lift 1.0 scores 500 and tops the list with no effect at
  all, while its excess is 0.
- Each lift carries Aito's own probability interval where the query
  returns one. No interval is computed in Python (rule 2).

## Breaks in the data, marked on every trend

- **The consent break (7.11.2026).** Analytics consent began then, so
  counts before and after don't compare. Each trend marks the date, and
  week-over-week cards prefer ratios across it.
- **Beta traffic.** beta.aito.ai sends to the same Amplitude project.
  Its pages already land host-first (`beta.aito.ai/…`), but its sessions
  count in the totals. Each session gets a `site` value, read from the
  events' `host` property (sent on every event since the website's
  33de0a28, not shipped yet) and else from Amplitude's page domain. The
  view defaults to `site = aito.ai`. A session with neither is site
  `unknown`, shown as such, never folded into the aito.ai default.
- **Bots** stay out, as now, and are counted in a footnote.

## The view (laid out like the e-commerce Analytics page)

- **Left: Compare by.** KPI tiles: sessions, onward, pricing, contact,
  sign-in, **sign-up click**, sandbox, first query. A click on a sign-up
  CTA is not an account; an **account created** tile appears only once the
  console reports one. **Every tile switches the whole
  right side**, including the onward and sign-up tiles. That fixes
  today's bug, where Sessions and Sign-up CTA still show the onward-click
  relations.
- **Left: Segment.** Filters as checkbox groups with counts: source,
  channel, campaign, landing vertical, device, first-touch, consultative
  stage. Choosing values narrows everything on the right.
- **Right: the trend.** The KPI over time, the chosen period against the
  one before it (dashed), with the consent break marked.
- **Right: tabs.**
  - **Highlights.** What goes with the KPI (`_relate`), ranked by excess,
    n ≥ 5, with n.
  - **Before.** The pages and events seen before reaching it, and the top
    paths into it (docs/37's `$patterns`), side by side with the top paths
    into a high-intent exit.
  - **Acquisition.** First touch, source, campaign and post (`_relate`
    over web_visitors and posts by utm).
  - **Content.** The second direction, described next.
  - **Journeys.** Internal only, as now.

## Content and what goes with it (the second direction)

Choose a content item: a post, a page, a demo, a consultative stage, or a
CTA variant. Then compare sessions that saw it with those that didn't,
for every KPI at once:

| KPI | saw it | didn't | lift (vs didn't) | n |
|---|---|---|---|---|

This is one `_relate` per item, with the item as the condition and each
KPI as the target.

- **"Didn't" is subtracted, not modelled.** A `_relate` lift is measured
  against *all* sessions, not against those that didn't see the item. For
  a page most sessions see (the home page), the two differ a lot. "Didn't"
  is the response's own 2×2 counts minus the "saw it" row; that's
  lookups, not statistics. Each lift says which baseline it's against.
- **It's association, not effect.** Sessions that see more pages see more
  items *and* reach more KPIs, so nearly every item shows lift above 1.
  The view says "goes with", never "effect" or "drives". Each item gets one
  comparison row, **any page at the same depth**: sessions that saw the
  same number of pages, whichever pages they were. An item only stands
  out if it beats that row.

Plus:

- **The exit after it.** The share of sessions whose last page was this
  one. This answers "does it make people drop out?", from web_steps.
- **Posts.** Attributed by `utm_campaign` (docs/36). A post with untagged
  links shows "untagged: unattributed", never zero. The cause gets fixed
  too: `add_post` and `set_post_link_path` warn when a link to aito.ai has
  no `utm_campaign` (its own small fix).
- **Demos.** Opened vs not, for every KPI, plus the exit after the demo.
- **CTA variants.** `Signup CTA clicked.variant`, each arm against the
  others.

## The consultative layer (from the website session)

Live only on beta.aito.ai since 8.11.2026, with little traffic yet. What
reaches Amplitude, after consent:

- `Consultative: stage`: `stage` ∈ {exploring, building, need, partner, null},
  `where`, `previous`, `change`, `dismissed`. Fixed sets, no free text.
- `Signup CTA clicked`: `variant`, `button`, `position`, `path`.

Coming with the website's next release (approved by Antti, not shipped
yet; the commit is still being amended after the CRO's review):
user properties set with consent only, all fixed categories: `interests`
(a sorted, space-joined subset of tech, usecases and ai), `domain`
(accounting, erp, ecommerce, service, agents or other) and `stage`.
Amplitude is set not to store IP addresses (verify on one beta event
after it deploys).

**Pulled:** `stage`, `domain` and `interests` as session attributes, so
they become segments and content items. A value outside its fixed set
raises with the row (rule 3). **Never pulled:** `words`, the visitor's own sentence. If
direct mode ever sends it to Amplitude, the pull drops it in memory, with
a test. The beta's own Aito events table (impressions, arms) is not ours
to read; it waits for direct mode.

## Known gaps this fixes

- **Which funnel is ours.** `funnel("website")` is the demo's synthetic data;
  the CRO's "all zeros" came from calling it on internal, where its table is
  empty (the CRO's own correction, 11.11.2026). Not a bug in the real funnel.
  Use `funnel("web")`, aito.ai's real traffic as reach per stage (#99). An
  empty funnel table now says so (#97), and week prep lists it as no data.
- **No onward rate per campaign.** The CRO rebuilt it from steps by hand.
- **The visit-KPI tiles** (Sessions, Onward, Sign-up CTA) don't switch the
  relations (today's bug).

## Build order (each slice fail-first)

1. **Bugs, each with a failing test first.** *Built 10–11.11.2026 (#97,
   #99), apart from `site`:*
   - **The KPI tiles.** Each relates its own outcome. A frontend test checks
     that choosing Sign-up click shows its own relations, not the onward ones.
   - **The pricing KPI** is matched by URL.
   - **An empty funnel table** says so.
   - **`funnel("web")`** reads the real visits as reach per stage. A truly
     ordered funnel from `web_steps`' order is a later option.
   - **Still to build:** the `site` value, with the aito.ai default and
     `unknown`.
2. **Honest counts.** n ≥ 5, ranking by excess, consent-break marks.
3. **Content → effect.** The Content tab: posts, pages, demos, variants.
4. **The layout.** The Segment checkboxes and the comparison trend.
5. **The consultative stage**, once prod has it.
6. **Account created, joined to the landing** (later). The sign-up link
   carries `from=landing&interests=&domain=&stage=`; if the console ever
   logs those on account creation, a click joins to an account. That needs
   an owner on the console side.

## Decisions for review

*Settled by Antti, 10.11.2026:* decision 1 as recommended (site aito.ai by
default, n ≥ 5, ranking by excess), and decision 2, pulling the
consultative choices. Also from Antti that day: the pricing KPI counts
aito.ai's own `/pricing/` page by its full URL, not the demo's pricing
estimator; his own visits and obvious crawlers should be left out (the
next slice); and more insights in a scrolling list.

1. **The defaults**, which are Antti's: the `site` default (aito.ai); the
   n ≥ 5 floor; and ranking Highlights by excess (example: a page seen in
   500 sessions at lift 1.0 has excess 0, so it doesn't top the list the
   way it would under count × lift). *The CPO recommends all three.*
2. **Pulling `stage`** from the consultative event. *Antti.*
3. **Known signed-in visitors in `who_to_call`** stays parked. *Antti.*
