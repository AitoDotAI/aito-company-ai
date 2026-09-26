# Queue before

sc024 Zara Day $p=0.3130
sc011 Zara Pike $p=0.2754
sc016 Grace Lane $p=0.2568
sc037 Grace Marsh $p=0.2291
sc054 Carol Vale $p=0.2202

# Log a touch for the top contact

{"booked": false, "channel": "call", "contact_id": "sc024", "days_since_prev_touch": "22+", "good_outcome": true, "next_action": "send pricing summary", "next_action_due": "2026-06-15", "notes": "picked up, good chat", "outcome": "conversation", "reached": true, "touch_id": "log-20260612081000-sc024", "ts": "2026-06-12T08:10:00", "weekday": "fri", "window": "0800"}

# Queue after

sc016 Grace Lane $p=0.3092
sc037 Grace Marsh $p=0.3000
sc011 Zara Pike $p=0.2971
sc054 Carol Vale $p=0.2771
sc013 Grace Ford $p=0.2741

change confirmed: sc024 left the queue, order shifted

# The new follow-up appears in what_changed

[
  {
    "company": "Vance BV",
    "contact_id": "sc024",
    "due": "2026-06-15",
    "name": "Zara Day",
    "next_action": "send pricing summary"
  }
]
