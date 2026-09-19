# Query 3: what changed


## Aito calls

request:  {"from": "touches", "limit": 100, "where": {"ts": {"$gte": "2026-06-11T00:00:00"}}}
response: total=4 (rows omitted)
request:  {"from": "touches", "limit": 100, "where": {"next_action_due": {"$gt": "", "$lte": "2026-06-15"}}}
response: total=6 (rows omitted)

## Derived

{
  "follow_ups_due": [
    {
      "company": "Genco Oy",
      "contact_id": "yc007",
      "due": "2026-05-13",
      "name": "Niaj Snow",
      "next_action": "send one-pager"
    },
    {
      "company": "Sabre BV",
      "contact_id": "yc006",
      "due": "2026-06-03",
      "name": "Yvonne Gray",
      "next_action": "send pricing summary"
    }
  ],
  "since_yesterday": [
    {
      "channel": "call",
      "company": "Sirius Oy",
      "name": "Quinn Snow",
      "notes": null,
      "outcome": "no_answer",
      "ts": "2026-06-11T12:24:00"
    },
    {
      "channel": "call",
      "company": "Pierce Oy",
      "name": "Peggy Stone",
      "notes": "good chat, asked about pricing",
      "outcome": "conversation",
      "ts": "2026-06-11T16:11:00"
    },
    {
      "channel": "call",
      "company": "Cobalt Oy",
      "name": "Quinn Ford",
      "notes": null,
      "outcome": "no_answer",
      "ts": "2026-06-11T16:56:00"
    },
    {
      "channel": "email",
      "company": "Cobalt Oy",
      "name": "Quinn Ford",
      "notes": null,
      "outcome": "no_reply",
      "ts": "2026-06-11T17:24:00"
    }
  ]
}

# Query 1: who to call, window 0800


## Aito calls

request:  {"from": "contacts", "limit": 10000}
response: total=10 (rows omitted)
request:  {"from": "touches", "limit": 10000}
response: total=15 (rows omitted)
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "none", "contact_id.segment": "erp", "contact_id.tier": "C", "days_since_prev_touch": "first", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.3544475079473707, "$value": "reply"}, {"$p": 0.23698903441521904, "$value": "no_reply"}, {"$p": 0.141888363470936, "$value": "conversation"}, {"$p": 0.09696445709863845, "$value": "no_answer"}, {"$p": 0.09573406327777988, "$value": "declined"}, {"$p": 0.07397657379005598, "$value": "callback_requested"}], "offset": 0, "total": 6}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "none", "contact_id.segment": "erp", "contact_id.tier": "C", "days_since_prev_touch": "first", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.3544475079473707, "$value": "reply"}, {"$p": 0.23698903441521904, "$value": "no_reply"}, {"$p": 0.141888363470936, "$value": "conversation"}, {"$p": 0.09696445709863845, "$value": "no_answer"}, {"$p": 0.09573406327777988, "$value": "declined"}, {"$p": 0.07397657379005598, "$value": "callback_requested"}], "offset": 0, "total": 6}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "shipped", "contact_id.segment": "ecommerce", "contact_id.tier": "A", "days_since_prev_touch": "8-21", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.2758181096374647, "$value": "reply"}, {"$p": 0.2396283528044679, "$value": "no_reply"}, {"$p": 0.17171176406505373, "$value": "no_answer"}, {"$p": 0.13270362195900298, "$value": "conversation"}, {"$p": 0.10122337545549301, "$value": "declined"}, {"$p": 0.07891477607851764, "$value": "callback_requested"}], "offset": 0, "total": 6}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "announced", "contact_id.segment": "accounting", "contact_id.tier": "C", "days_since_prev_touch": "first", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.30892247235557996, "$value": "no_reply"}, {"$p": 0.2892500144488576, "$value": "reply"}, {"$p": 0.12468360193333547, "$value": "conversation"}, {"$p": 0.10798238257825463, "$value": "declined"}, {"$p": 0.10162318697205297, "$value": "no_answer"}, {"$p": 0.06753834171191922, "$value": "callback_requested"}], "offset": 0, "total": 6}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "shipped", "contact_id.segment": "consultancy", "contact_id.tier": "B", "days_since_prev_touch": "22+", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.3500148383891098, "$value": "no_reply"}, {"$p": 0.2688490941281822, "$value": "reply"}, {"$p": 0.10649729591212805, "$value": "declined"}, {"$p": 0.10251669219688073, "$value": "no_answer"}, {"$p": 0.10129752270034094, "$value": "conversation"}, {"$p": 0.07082455667335831, "$value": "callback_requested"}], "offset": 0, "total": 6}

## Derived

[
  {
    "$p": 0.21586493726099198,
    "company": "Tyrell Oy",
    "contact_id": "yc002",
    "name": "Mona Fields",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "none",
      "days_since_prev_touch": "first",
      "segment": "erp",
      "tier": "C",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.21586493726099198,
    "company": "Wayne GmbH",
    "contact_id": "yc010",
    "name": "Sybil Stone",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "none",
      "days_since_prev_touch": "first",
      "segment": "erp",
      "tier": "C",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.21161839803752064,
    "company": "Sabre BV",
    "contact_id": "yc006",
    "name": "Yvonne Gray",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "shipped",
      "days_since_prev_touch": "8-21",
      "segment": "ecommerce",
      "tier": "A",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.1922219436452547,
    "company": "Hanso Oy",
    "contact_id": "yc003",
    "name": "Rupert Brooks",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "announced",
      "days_since_prev_touch": "first",
      "segment": "accounting",
      "tier": "C",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.17212207937369925,
    "company": "Genco Oy",
    "contact_id": "yc007",
    "name": "Niaj Snow",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "shipped",
      "days_since_prev_touch": "22+",
      "segment": "consultancy",
      "tier": "B",
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
response: total=2 (rows omitted)
request:  {"from": "contacts", "limit": 1000, "select": ["contact_id", "name", "company", "segment", "tier", "ai_lifecycle"], "where": {"contact_id": {"$or": ["yc006", "yc008"]}, "segment": "erp"}}
response: total=1 (rows omitted)

## Derived

[
  {
    "ai_lifecycle": "announced",
    "company": "Pierce Oy",
    "evidence": {
      "channel": "call",
      "notes": "good chat, asked about pricing",
      "outcome": "conversation",
      "ts": "2026-06-11T16:11:00",
      "window": "1600"
    },
    "segment": "erp",
    "similar_contact": "Peggy Stone",
    "tier": "A"
  }
]
