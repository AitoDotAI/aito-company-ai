# The messaging formula (post scorer)

Marketing (the view formerly called Distribution) is where the daily content
decision lives. It is three tables:

- **materials** — the content catalog (a blog post, a demo, a whitepaper);
  the content's attributes (topic, lane, ai_made, length) live here.
- **channels** — the destination catalog (Hacker News, r/programming,
  LinkedIn, the blog). A channel rolls up to a **platform**.
- **posts** — a material posted (or planned) to a channel: the go/no-go
  lifecycle (`planned → go / no_go → posted`), the post-level details (tone,
  format, link placement), and the KPIs once posted. The material's and
  channel's attributes denormalize onto the post at load, so the scorer's
  prediction stays a single query.

The scorer predicts whether a draft will *win* on its **platform** and
explains which lever moves that prediction — the dogfood moment: *our own
predictive DB tells us which post will land, and why.* Channels roll up to
platforms, so the scorer has enough data per platform and sharpens per
channel as posts accrue.

## The success metric, encoded (the one thing to get right)

Per `operator-ground-truth.md` §3: the target is **per channel**.

- **LinkedIn → reach. Hacker News → views. Never upvotes.**

`upvotes` is logged but is *never* the target, so the "quiet win" (high
views, low upvotes) stays visible and the model never optimizes for points.
This is encoded structurally: the scorer predicts the boolean `won`, and
`won` is defined per channel from `reach_or_views` (reach for LI, views for
HN), not from upvotes. Point the model at the wrong column and it
recommends the wrong posts — so the column choice is the design.

## The `posts` table

One row per shipped post — features only, **no free-text title** (titles
can carry customer names; we keep the feature vector). Loaded by
`company-ai load-posts` (`--seed`, or real data via `COMPANY_AI_DATA_DIR/
posts.csv`). Schema in `docs/02-schema.md`. Derived at load: `weekday`
(from `posted_at`), `length_bucket` (from `length_chars`), and `won`
(`outcome == win`).

## The scorer

Three kinds of Aito call (`scorer.py`), nothing computed in Python:

1. **P(win)** — `_predict won GIVEN (channel, tone, ai_made, format,
   link_placement, lane, topic, length_bucket, weekday)`. The draft's
   calibrated win probability.
2. **What moved it** — the `$why` per-feature contribution on that
   prediction (base rate × each feature's lift). This is the explanation,
   and it is the product.
3. **Levers** — `_recommend` the best value of each actionable lever
   (`tone`, `link_placement`, `ai_made`) toward `won = true`, filtered to
   values that actually occur on the channel so it never suggests an
   off-channel combination (a first-comment link on HN). `format` and
   `weekday` are deliberately not levers — one is channel-defining, the
   other too noisy at this data size.

The doctrine the seed plants and the scorer recovers: **narrate ≫
announce**, a LinkedIn **link in the body craters reach ~10×** vs the first
comment, **HN is binary**, and **AI-voice gets buried on general channels**.

## Using it

```sh
uv run company-ai load-posts --seed
uv run company-ai dashboard          # http://localhost:8770/scorer
```

Pick the draft's features; the page shows P(win), the channel base rate,
the per-feature contribution, and the lever switches. Also the `score_post`
MCP tool, so a Claude session can score a draft in chat.

## Cold start

The HN history is thin; until the own `posts` log deepens (~15–20 HN
rows), the scorer is honestly under-confident on HN — correct behavior, not
a bug. `operator-ground-truth.md` §3 carries the public-HN priors to blend
in as the log fills. The fastest path to a sharp scorer is logging every
shipped post from now on.

## Not modelled yet

`clicks`, `comments`, and a `predicted`-vs-actual calibration history are
out of scope for v1; `trials` is carried for judging cold/PLG drops by
activation rather than upvotes (per the two-funnel rule, `docs/09`).
