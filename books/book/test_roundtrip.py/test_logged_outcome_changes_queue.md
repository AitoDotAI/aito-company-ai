# Queue before

sc024 Zara Day $p=0.3108
sc011 Zara Pike $p=0.2532
sc016 Grace Lane $p=0.2340
sc037 Grace Marsh $p=0.2146
sc038 Victor Brooks $p=0.1949

# Log a touch for the top contact

{"booked": false, "channel": "call", "company_id": "vance-bv", "contact_id": "sc024", "days_since_prev_touch": "22+", "good_outcome": true, "hour": 8, "next_action": "send pricing summary", "next_action_due": "2026-06-15", "notes": "picked up, good chat", "outcome": "conversation", "reached": true, "step": 4, "touch_id": "log-20260612081000-sc024", "ts": "2026-06-12T08:10:00", "weekday": "fri", "window": "0800"}

# Queue after

sc016 Grace Lane $p=0.2949
sc037 Grace Marsh $p=0.2932
sc011 Zara Pike $p=0.2771
sc013 Grace Ford $p=0.2528
sc038 Victor Brooks $p=0.2329

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
