# Queue before

sc014 Eve Fields $p=0.3821
sc021 Victor Vale $p=0.3413
sc015 Carol Gray $p=0.2988
sc049 Mona Hill $p=0.2784
sc002 Judy Lake $p=0.2683

# Log a touch for the top contact

{"booked": false, "channel": "call", "contact_id": "sc014", "days_since_prev_touch": "8-21", "good_outcome": true, "next_action": "send pricing summary", "next_action_due": "2026-06-15", "notes": "picked up, good chat", "outcome": "conversation", "reached": true, "touch_id": "log-20260612081000-sc014", "ts": "2026-06-12T08:10:00", "weekday": "fri", "window": "0800"}

# Queue after

sc021 Victor Vale $p=0.6665
sc015 Carol Gray $p=0.6152
sc048 Dave Pike $p=0.5511
sc032 Judy Pike $p=0.5294
sc002 Judy Lake $p=0.4943

change confirmed: sc014 left the queue, order shifted

# The new follow-up appears in what_changed

[
  {
    "company": "Sterling BV",
    "contact_id": "sc014",
    "due": "2026-06-15",
    "name": "Eve Fields",
    "next_action": "send pricing summary"
  }
]
