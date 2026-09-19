# 14 · Experiments — the learning pipeline

A one-person company's scarcest resource is not leads or code, it is
*validated learning*: which bets actually move a metric. This pipeline makes
that loop a first-class table, in the Lean Startup spirit (Build → Measure →
Learn), and — like every other surface here — hands the judgement to Aito
rather than to Python.

## What an experiment is

One row in the `experiments` table is one falsifiable bet:

- a **hypothesis** ("a guided first-run lifts trial_start_rate from 0.3 to
  0.45"),
- the one **metric** it means to move, its **baseline**, and the **target**
  that would validate it,
- the **area** it touches — the AARRR funnel stage (acquisition, activation,
  revenue, retention, referral), so an experiment ties to the funnel it is
  trying to bend (`docs/09-funnels.md`),
- the **effort** to build it (small / medium / large), and
- a **status**: `running` while in flight, then a terminal verdict —
  `validated`, `invalidated`, or `inconclusive` — or `abandoned` if killed
  before a verdict. A verdict carries the measured **result** and the
  **learning**.

`validated` is derived (true on `validated`, false on `invalidated`, null
otherwise) — it is the predictor target, exactly like `deals.won` and
`posts.won`.

## The two reads (`experiments.py`)

**Descriptive** (counts → rate, formatting only): the validated-learning rate
(`validated / decided`), the status mix, and the live board of running bets.

**Predictive** (Aito, the whole point): `_predict validated GIVEN effort`
(and by area) — *which kinds of experiment tend to pay off?* The seed plants
the Lean doctrine that small, cheap bets validate more often than large ones
(small ≈ 74%, large ≈ 20% on the seed), and the board recovers it
(`favour_small`). On real, thin data the rates and the predicted
P(validated) are weak and wide — that is the loop working, shown honestly,
not a defect.

## The loop is closed

- **Build** — `add_experiment` starts a `running` bet (MCP tool, or the
  dashboard's agent path).
- **Measure / Learn** — `log_experiment_result` records the measured result
  and a terminal verdict, re-deriving `validated` and re-ranking the board.
  A result without a terminal verdict is refused (loud), and a verdict
  without a result is refused at load — a half-finished bet cannot pretend to
  be evidence.

## Surfaces

- **Agent**: `experiment_board`, `add_experiment`, `log_experiment_result`
  over MCP; the populate prompt lists them.
- **Human**: the **Experiments** view (its own LEARNING group in the nav) —
  the KPI row, the P(validated)-by-effort bars, and the running-bets board.
  Its Data tab is the raw `experiments` sheet.
- **CLI**: `company-ai load-experiments [--seed]`; `export experiments` round-
  trips like every other table.

## What is deliberately not here

No automatic experiment *generation* and no auto-resolution: the agent
proposes and the operator decides, the same contract as everywhere else. The
pipeline records bets and tells you which kinds have paid off; it does not
run them for you.
