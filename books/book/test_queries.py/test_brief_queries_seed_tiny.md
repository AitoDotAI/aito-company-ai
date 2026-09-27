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
response: {"hits": [{"$p": 0.3651610164056862, "$value": "meeting_booked"}, {"$p": 0.2449204983273895, "$value": "reply"}, {"$p": 0.16700632867973955, "$value": "no_reply"}, {"$p": 0.1524214550680594, "$value": "no_answer"}, {"$p": 0.0704907015191254, "$value": "callback_requested"}], "offset": 0, "total": 5}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "announced", "contact_id.segment": "consultancy", "contact_id.tier": "C", "days_since_prev_touch": "first", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.35410329393047185, "$value": "meeting_booked"}, {"$p": 0.2300245027129004, "$value": "reply"}, {"$p": 0.20788148477730423, "$value": "no_reply"}, {"$p": 0.1315987700324968, "$value": "no_answer"}, {"$p": 0.07639194854682672, "$value": "callback_requested"}], "offset": 0, "total": 5}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "none", "contact_id.segment": "analytics", "contact_id.tier": "B", "days_since_prev_touch": "8-21", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.2801506177247798, "$value": "no_reply"}, {"$p": 0.2590339860925988, "$value": "meeting_booked"}, {"$p": 0.16344202708305003, "$value": "reply"}, {"$p": 0.15264580877730322, "$value": "no_answer"}, {"$p": 0.14472756032226827, "$value": "callback_requested"}], "offset": 0, "total": 5}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "none", "contact_id.segment": "analytics", "contact_id.tier": "C", "days_since_prev_touch": "first", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.30478240173281734, "$value": "no_reply"}, {"$p": 0.25954632157222624, "$value": "meeting_booked"}, {"$p": 0.18148043588835402, "$value": "reply"}, {"$p": 0.13355457703349394, "$value": "no_answer"}, {"$p": 0.1206362637731084, "$value": "callback_requested"}], "offset": 0, "total": 5}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "none", "contact_id.segment": "consultancy", "contact_id.tier": "C", "days_since_prev_touch": "first", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.31429268282447276, "$value": "no_reply"}, {"$p": 0.27967334778582204, "$value": "meeting_booked"}, {"$p": 0.17700421500127, "$value": "reply"}, {"$p": 0.1344478632555045, "$value": "no_answer"}, {"$p": 0.09458189113293065, "$value": "callback_requested"}], "offset": 0, "total": 5}

## Derived

[
  {
    "$p": 0.4356517179248116,
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
    "$p": 0.4304952424772986,
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
    "$p": 0.40376154641486706,
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
    "$p": 0.38018258534533467,
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
    "$p": 0.3742552389187527,
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
