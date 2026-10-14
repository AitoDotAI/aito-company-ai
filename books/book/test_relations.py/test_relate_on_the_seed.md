# What goes with reaching a person (touches)

request: {"from": "touches", "limit": 300, "relate": {"reached": true}}
population 150, with outcome 70
  hour=17             lift 1.33  mi 0.0083  rate 0.833 vs 0.435  rows 12
  window=1600           lift 1.13  mi 0.0039  rate 0.595 vs 0.425  rows 37
  days_since_prev_touch=0-2            lift 0.77  mi 0.0032  rate 0.267 vs 0.489  rows 15
  hour=14             lift 0.77  mi 0.0032  rate 0.267 vs 0.489  rows 15
  window=other          lift 0.86  mi 0.0026  rate 0.345 vs 0.496  rows 29
  window=0800           lift 0.92  mi 0.0020  rate 0.396 vs 0.505  rows 53
  days_since_prev_touch=8-21           lift 1.08  mi 0.0019  rate 0.542 vs 0.431  rows 48
  step=6              lift 1.15  mi 0.0017  rate 0.75 vs 0.459  rows 4  THIN
excluded: booked, calendar_event_id, company_id, contact_id, deal_id, gmail_thread_id, good_outcome, next_action, next_action_due, notes, outcome, reached, touch_id, ts

# Within calls only

request: {"from": "touches", "limit": 300, "relate": {"$on": [{"reached": true}, {"channel": "call"}]}}
population 57, with outcome 27
  hour=17             lift 1.26  mi 0.0124  rate 0.778 vs 0.417  rows 9  THIN
  window=1600           lift 1.14  mi 0.0089  rate 0.619 vs 0.389  rows 21
  step=6              lift 1.23  mi 0.0071  rate 1.0 vs 0.455  rows 2  THIN
  step=5              lift 0.50  mi 0.0060  rate 0.0 vs 0.491  rows 2  THIN
  hour=8              lift 0.81  mi 0.0059  rate 0.308 vs 0.523  rows 13
  weekday=thu            lift 0.81  mi 0.0059  rate 0.308 vs 0.523  rows 13
excluded: booked, calendar_event_id, channel, company_id, contact_id, deal_id, gmail_thread_id, good_outcome, next_action, next_action_due, notes, outcome, reached, touch_id, ts

# What goes with losing a deal (deals)

request: {"from": "deals", "limit": 300, "relate": {"won": false}}
population 280, with outcome 179
  champion_present=False          lift 1.22  mi 0.0511  rate 0.795 vs 0.51  rows 127
  champion_present=True           lift 0.82  mi 0.0511  rate 0.51 vs 0.795  rows 153
  blocker=none           lift 0.67  mi 0.0435  rate 0.4 vs 0.719  rows 70
  segment=accounting     lift 0.87  mi 0.0078  rate 0.519 vs 0.687  rows 79
  blocker=budget         lift 1.13  mi 0.0053  rate 0.796 vs 0.606  rows 49
  blocker=timing_mismatch lift 1.12  mi 0.0039  rate 0.805 vs 0.611  rows 41
excluded: company_id, created, deal_id, first_meeting_date, last_touch_date, lost_reason, search_text, search_title, stage, won

# A field the table does not have is refused

refused: touches has no field 'no_such_field'
