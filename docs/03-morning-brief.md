# The morning brief

Three queries, specified here so they are implemented, not improvised.

## Query 1: who to call now

`_query` over contacts joined with touch history, ordered by

```
$p( outcome in {conversation, meeting_booked, callback_requested}
    | window = current, weekday = current,
      segment, tier, ai_lifecycle, days_since_last_touch )
```

Exclusions, applied before ranking:
- contacts with an open `next_action` not yet due (they are in the
  follow-up list instead)
- contacts touched within the last N days (N configurable, default 5)
- contacts with `phone_present = false` when window is a call window
  (they are reach, not pipeline)

Output: top 5 with `$p` shown. Small data makes early `$p` weak; show it
anyway. Weak-and-honest is the design working.

## Query 2: opener context

For each queued contact, `_match` / `_similarity` against past touches of
statistically similar contacts (conditioning on segment, tier,
ai_lifecycle) that ended in `conversation` or `meeting_booked`. Return the
2-3 most similar with their outcomes and notes.

The statistics retrieve; Claude writes. The suggested opener is drafted by
the reasoning layer from retrieved evidence, never templated in Python.

## Query 3: what changed

`_query` over touches where `ts >= yesterday`, plus every row where
`next_action_due <= today + 72h`. The 72-hour horizon encodes the standing
rule that every email is paired with a call within 72 hours.

Output: a flat follow-up list, due-first.

## Brief format

Target: one phone screen in the no-llm rendering.

```
DO NEXT (today, all areas)
  P<priority> <action>  (<due / overdue / area>)  [⚠ slip <p> if high]
  ...

FOLLOW-UPS (due)
  <name, company>  <next_action>  due <date>
  ...

CALL QUEUE  <window>  <weekday>
  1. <name, company>   $p=0.41   why: <one line>
     opener angle: <one line from similar-contact evidence>
  ...

SEGMENT READ  conversion vs pipeline <p>
  <segment>  <rate> <arrow>   best window <window>
  ...
```

## Do next

Action-first: the brief opens with the cross-area Now list (`docs/12`) — the
most urgent open todos across all areas, overdue first, each carrying Aito's
slip-risk so a likely-to-slip action (⚠) is shored up before the call window.
The no-llm brief uses `todos.now`; the LLM path calls `todos_now`.

## Segment read

A 360 footer that wires the Segment 360 analysis (`docs/07-dashboard.md`)
into the brief: for each distinct segment in today's queue, its conversion
rate against the whole-pipeline baseline and the window it converts best in
(the conversion lever). It answers "which queued segments are hot, and am I
calling them at their best window" — e.g. a segment marked best at 1600
while the current window is 0800 is a prompt to reschedule. The no-llm
rendering uses `analytics.kpi_read` (two Aito calls per segment); the LLM
path calls the `segment_360` tool.

## Logging loop

After-call logging must cost under 15 seconds:
- CLI shorthand: `log <contact> call 0800 no_answer`
- or one sentence to Claude, which calls `log_touch`

When the operator reorders or skips the recommended queue, that is a
`decisions` row (`human_action = overridden`), captured via `log_decision`.
Every logged touch is immediately queryable: the round-trip booktest
verifies that a logged outcome changes the next `who_to_call` result.
