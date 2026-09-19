# Phases

Budget: ~10 hours total. When a phase overruns, cut features from the
phase; never extend the budget silently.

## Phase A: schema + loaders (~3h)

Aito table creation script; `load-rolodex` and `load-touches` CLI reading
from `COMPANY_AI_DATA_DIR` or `data/seed/` with `--seed`; idempotent
upserts. Synthetic seed data committed (see `06-privacy.md`). README
written, as if public, in this phase.

Done when: loader gate green on both datasets; seed data passes the
privacy grep.

## Phase B: MCP server (~3h)

The six tools from `01-architecture.md`, thin wrappers only. One-line
registration documented in README for Claude Code and Claude Desktop.

Done when: each tool has a reviewed booktest snapshot against seed data.

## Phase C: the brief (~2h)

`prompts/morning-brief.md` and `brief --no-llm`.

Done when: query gate green on both datasets; no-llm brief fits one phone
screen; one real morning use by the operator.

## Phase D: the loop (~2h)

`log` CLI shorthand, `log_touch` and `log_decision` wired into the brief
flow.

Done when: round-trip gate green; logging a real call takes under 15
seconds end to end.

## Gated: Head 2 (external support agent)

Predict-first support agent over public docs and past tickets, confidence-
gated from day one (above threshold answers, below escalates to the
operator). GATED on Head 1 running for two real weeks. Do not scaffold,
do not stub, propose-and-park only.

## Phase E: Segment 360 dashboard

A read-only web dashboard over the same Aito queries: per-segment KPI
rates, their root causes (`_relate`), and the lever that moves each
(`_recommend`). Important for a human operator and for showing the system
off. Spec in `docs/07-dashboard.md`.

Done when: `analytics.segment_360` is booktested on both datasets and
`company-ai dashboard` renders the KPI cards.

## Phase F: predictive funnels

Website/acquisition funnel (`sessions`: visitor → signup → trial → paid)
and the sales funnel (over `contacts`). Each stage shows step conversion,
the biggest-drop leak, Aito's calibrated outlook (`_predict`), the leak's
causes (`_relate`), and the lever (`_recommend`). Rendered in the
dashboard's Funnels tab and exposed as the `funnel` MCP tool. Spec in
`docs/09-funnels.md`.

Done when: `funnels.funnel` is booktested for both funnels on both
datasets and the Funnels tab renders.

## Phase G: messaging formula (post scorer)

The `posts` distribution log + the scorer: `_predict won GIVEN` a draft's
features per channel, the `$why` per-feature contribution, and the lever
(`_recommend`) that most raises the win probability. Target is per channel
(LinkedIn reach / HN views, never upvotes). Dashboard "Post scorer" tab and
the `score_post` MCP tool. Spec in `docs/10-messaging-formula.md`.

Done when: `scorer.score` is booktested on both datasets and the scorer tab
renders the prediction, the contribution, and the levers.

## Phase H: action surface (todos + Now)

The unified `todos` table and the three lenses (now / pipeline / calendar)
that make the dashboard action-first: a cross-area Now landing view, and
each Work view opening with its action block. Rule-based ordering (not
inference) for now; the Aito slip-risk layer follows once todo history
accrues. `todos_now` / `todos_area` MCP tools feed the same surface into the
brief. Spec in `docs/12-todos-and-now.md`.

Done when: the three lenses are booktested on both datasets and the Now view
plus the Work action blocks render.

## Phase I: deals pipeline + close-likelihood

The `deals` table (open pipeline + closed history), the weighted-pipeline
KPIs, and Aito's per-deal close-likelihood (`_predict won GIVEN stage,
blocker, champion_present`) with `$why`, shown in the Sales view beside the
operator's own probability. The closed loop: `log_deal_update` advances a
deal (the deals analog of the touch round-trip), exposed as `deal_pipeline`
and `log_deal_update` MCP tools. Spec in `docs/13-deals.md`.

Done when: `deals.pipeline` and the update round-trip are booktested on both
datasets and the Sales pipeline block renders.

## Banned without explicit operator decision

Outbound automation (sending email, LinkedIn actions, calendar writes),
schedulers, additional decision domains.
