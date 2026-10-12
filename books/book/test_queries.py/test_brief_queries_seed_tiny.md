# Query 3: what changed


## Aito calls

request:  {"from": "touches", "limit": 100, "where": {"ts": {"$gte": "2026-06-11T00:00:00"}}}
response: total=4 (rows omitted)
request:  {"from": "touches", "limit": 100, "where": {"next_action_due": {"$gt": "", "$lte": "2026-06-15"}}}
response: total=5 (rows omitted)

## Derived

{
  "follow_ups_due": [
    {
      "company": "Genco Oy",
      "contact_id": "yc009",
      "due": "2026-06-03",
      "name": "Zara Wells",
      "next_action": "call back"
    },
    {
      "company": "Rekall Oy",
      "contact_id": "yc005",
      "due": "2026-06-04",
      "name": "Heidi Pike",
      "next_action": "send one-pager"
    }
  ],
  "since_yesterday": [
    {
      "channel": "call",
      "company": "Nimbus GmbH",
      "name": "Mona Pike",
      "notes": null,
      "outcome": "no_answer",
      "ts": "2026-06-11T12:24:00"
    },
    {
      "channel": "email",
      "company": "Vertex O\u00dc",
      "name": "Carol Vale",
      "notes": "replied, lukewarm but open",
      "outcome": "reply",
      "ts": "2026-06-11T14:00:00"
    },
    {
      "channel": "linkedin",
      "company": "Rekall Oy",
      "name": "Carol Brooks",
      "notes": null,
      "outcome": "no_reply",
      "ts": "2026-06-11T17:24:00"
    },
    {
      "channel": "email",
      "company": "Vertex O\u00dc",
      "name": "Niaj Vale",
      "notes": null,
      "outcome": "no_reply",
      "ts": "2026-06-11T18:45:00"
    }
  ]
}

# Query 1: who to call, window 0800


## Aito calls

request:  {"from": "contacts", "limit": 10000}
response: total=10 (rows omitted)
request:  {"from": "touches", "limit": 10000}
response: total=15 (rows omitted)
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "announced", "contact_id.segment": "consultancy", "contact_id.tier": "A", "days_since_prev_touch": "8-21", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.4596471487792537, "$value": "meeting_booked"}, {"$p": 0.20037935383844677, "$value": "reply"}, {"$p": 0.15570834366195666, "$value": "no_reply"}, {"$p": 0.13668311145151255, "$value": "no_answer"}, {"$p": 0.047582042268830387, "$value": "callback_requested"}], "offset": 0, "total": 5}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "announced", "contact_id.segment": "consultancy", "contact_id.tier": "C", "days_since_prev_touch": "first", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.4122132719428438, "$value": "meeting_booked"}, {"$p": 0.24199579186409534, "$value": "no_reply"}, {"$p": 0.17404188505865792, "$value": "reply"}, {"$p": 0.10913710368050646, "$value": "no_answer"}, {"$p": 0.06261194745389666, "$value": "callback_requested"}], "offset": 0, "total": 5}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "none", "contact_id.segment": "analytics", "contact_id.tier": "B", "days_since_prev_touch": "8-21", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.3243171405878662, "$value": "meeting_booked"}, {"$p": 0.2598026225952949, "$value": "no_reply"}, {"$p": 0.1467234620495381, "$value": "callback_requested"}, {"$p": 0.13615281595151638, "$value": "no_answer"}, {"$p": 0.13300395881578436, "$value": "reply"}], "offset": 0, "total": 5}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "none", "contact_id.segment": "analytics", "contact_id.tier": "C", "days_since_prev_touch": "first", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.3534257853124684, "$value": "no_reply"}, {"$p": 0.3009700100960569, "$value": "meeting_booked"}, {"$p": 0.13678101825553993, "$value": "reply"}, {"$p": 0.11033053164844235, "$value": "no_answer"}, {"$p": 0.09849265468749259, "$value": "callback_requested"}], "offset": 0, "total": 5}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "none", "contact_id.segment": "consultancy", "contact_id.tier": "C", "days_since_prev_touch": "first", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.45978672234496415, "$value": "no_reply"}, {"$p": 0.2590891964875153, "$value": "meeting_booked"}, {"$p": 0.09982360274413452, "$value": "no_answer"}, {"$p": 0.0952759268746156, "$value": "reply"}, {"$p": 0.08602455154877058, "$value": "callback_requested"}], "offset": 0, "total": 5}

## Derived

[
  {
    "$p": 0.5072291910480841,
    "company": "Rekall Oy",
    "contact_id": "yc005",
    "name": "Heidi Pike",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "announced",
      "days_since_prev_touch": "8-21",
      "segment": "consultancy",
      "tier": "A",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.47482521939674044,
    "company": "Pied O\u00dc",
    "contact_id": "yc008",
    "name": "Peggy Pike",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "announced",
      "days_since_prev_touch": "first",
      "segment": "consultancy",
      "tier": "C",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.4710406026374043,
    "company": "Genco Oy",
    "contact_id": "yc009",
    "name": "Zara Wells",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "none",
      "days_since_prev_touch": "8-21",
      "segment": "analytics",
      "tier": "B",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.39946266478354947,
    "company": "Genco Oy",
    "contact_id": "yc002",
    "name": "Eve Pike",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "none",
      "days_since_prev_touch": "first",
      "segment": "analytics",
      "tier": "C",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.3451137480362859,
    "company": "Rekall Oy",
    "contact_id": "yc001",
    "name": "Zara Brooks",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "none",
      "days_since_prev_touch": "first",
      "segment": "consultancy",
      "tier": "C",
      "weekday": "fri",
      "window": "0800"
    }
  }
]

# Query 2: opener context for yc002


## Aito calls

request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "yc002"}}
response: total=1 (rows omitted)
request:  {"from": "touches", "limit": 1000, "where": {"contact_id": {"$not": "yc002"}, "outcome": {"$or": ["conversation", "meeting_booked"]}}}
response: total=3 (rows omitted)
request:  {"from": "contacts", "limit": 1000, "select": ["contact_id", "name", "company", "segment", "tier", "ai_lifecycle"], "where": {"contact_id": {"$or": ["yc004", "yc005", "yc010"]}, "segment": "analytics"}}
response: total=0 (rows omitted)

## Derived

[]
