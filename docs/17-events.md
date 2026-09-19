# 17 · Events to attend (the go/no-go board)

A record of events worth attending — conferences, meetups, webinars, talks,
sponsorships — each carrying a **go/no-go decision**. Same lifecycle shape as
posts: a `candidate` becomes `go` or `no_go`, and a `go` you actually went to
becomes `attended` with an outcome (`worthwhile` / `neutral` / `waste`).

## The table

`events`: `event_id`, `name`, `type`, `starts` (ISO date), `location`,
`cost_eur`, `status` (candidate/go/no_go/attended), `decided`, `outcome`,
`notes`, `created`. The outcome is graded only on an attended event — a
non-attended one claiming an outcome raises (rule 3).

## Surfaces

- **Events view** (WORK nav): a KPI row (candidates / going / attended), a
  week calendar of the ones you're going to, and the **go/no-go board** —
  each row has the decision buttons inline (Go / No-go on a candidate; the
  attended-outcome grades + drop on a go; reconsider on a no_go). The decision
  is recorded immediately.
- **Calendar**: `go` and `attended` events also show on the Sales and
  Marketing week grids alongside todos, so the week reads as a whole.
- **Agent / CLI**: `add_event` and `decide_event` MCP tools; `log.add_event` /
  `log.decide_event`; `company-ai load-events`. `export events` round-trips.

## Not (yet) predictive

This is a recorded decision loop, not an Aito prediction — the operator makes
the call. As attended outcomes accrue, Aito could later predict which kinds of
event tend to be worthwhile (by type / cost / location), the same way the post
scorer predicts a win; that's a parked extension, not built.
