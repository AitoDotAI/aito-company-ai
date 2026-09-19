# 15 · Week-prep composer

A short, grounded **Sunday prep** written for you once a week: what the coming
week should focus on, drawn entirely from the live pipeline. It is the one
surviving half of the old board cluster — the advisory persona board and the
Friday board-review were removed; week-prep stayed because it stands on its
own (no advisor roster) and feeds the [routines](18-routines.md) rhythm.

## The doctrine (CLAUDE.md rule 1, exception a)

The composition runs **server-side**, but the reasoning is *grounded*: every
fact comes from Aito — the same queries the dashboard and MCP use — and the
LLM only writes prose from those facts. It has **no tools and no autonomy**;
it never scores, ranks, or predicts (that is Aito's, always — rule 2), and it
never acts. Weak-and-honest beats confident-and-fabricated: it may cite only
the numbers Aito produced.

## The reads

`board.WEEK_PREP_READS` — a fixed planning set:

```
todos_now · todos_area · deal_pipeline · experiment_board · funnel ·
score_post · what_changed
```

`gather()` collects those facts (deterministic given `as_of`); `assemble()`
builds the `(system, user)` messages (pure given its inputs); the LLM call is
the only non-deterministic step, and it is injected so a booktest can run the
whole pipeline with a fake composer (see `book/test_board.py`).

## Running it

- **CLI / cron:** `board-run` (wraps `board.run("week-prep.md", mode="plan")`),
  driven by `ops/board-run.sh` and the `company-ai-weekplan` /
  `company-ai-weekprep` systemd timers.
- Each run writes its output to `.briefs/` (gitignored) so a scheduled run is
  readable. `prepare` mode writes a draft; `plan` mode the live plan.

The prompt lives in `prompts/week-prep.md`; the composer in
`src/company_ai/board.py`. There is no dashboard trigger — week-prep is a
scheduled/CLI job, not an in-app button.
