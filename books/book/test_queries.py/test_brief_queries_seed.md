# Query 3: what changed


## Aito calls

request:  {"from": "touches", "limit": 100, "where": {"ts": {"$gte": "2026-06-11T00:00:00"}}}
response: total=6 (rows omitted)
request:  {"from": "touches", "limit": 100, "where": {"next_action_due": {"$gt": "", "$lte": "2026-06-15"}}}
response: total=50 (rows omitted)

## Derived

{
  "follow_ups_due": [
    {
      "company": "Encom O\u00dc",
      "contact_id": "sc021",
      "due": "2026-04-23",
      "name": "Victor Vale",
      "next_action": "send pricing summary"
    },
    {
      "company": "Tessier Ab",
      "contact_id": "sc040",
      "due": "2026-04-25",
      "name": "Victor Snow",
      "next_action": "send one-pager"
    },
    {
      "company": "Onyx Oy",
      "contact_id": "sc032",
      "due": "2026-05-09",
      "name": "Judy Pike",
      "next_action": "call back"
    },
    {
      "company": "Globex Oy",
      "contact_id": "sc028",
      "due": "2026-06-01",
      "name": "Frank Banks",
      "next_action": "call back"
    },
    {
      "company": "Pied BV",
      "contact_id": "sc002",
      "due": "2026-06-05",
      "name": "Judy Lake",
      "next_action": "send pricing summary"
    },
    {
      "company": "Widmore Oy",
      "contact_id": "sc018",
      "due": "2026-06-07",
      "name": "Peggy Lake",
      "next_action": "send one-pager"
    },
    {
      "company": "Duff BV",
      "contact_id": "sc006",
      "due": "2026-06-08",
      "name": "Peggy Fields",
      "next_action": "send one-pager"
    },
    {
      "company": "Rekall BV",
      "contact_id": "sc044",
      "due": "2026-06-09",
      "name": "Niaj Lake",
      "next_action": "prepare demo"
    },
    {
      "company": "Pendant Oy",
      "contact_id": "sc045",
      "due": "2026-06-10",
      "name": "Grace Lake",
      "next_action": "send one-pager"
    },
    {
      "company": "Oscorp O\u00dc",
      "contact_id": "sc010",
      "due": "2026-06-12",
      "name": "Hank Brooks",
      "next_action": "send one-pager"
    },
    {
      "company": "Hardman Oy",
      "contact_id": "sc043",
      "due": "2026-06-13",
      "name": "Yvonne Stone",
      "next_action": "send one-pager"
    },
    {
      "company": "Aperture Oy",
      "contact_id": "sc013",
      "due": "2026-06-15",
      "name": "Victor Hill",
      "next_action": "send one-pager"
    },
    {
      "company": "Wonka Oy",
      "contact_id": "sc003",
      "due": "2026-06-15",
      "name": "Mallory Hill",
      "next_action": "send pricing summary"
    }
  ],
  "since_yesterday": [
    {
      "channel": "linkedin",
      "company": "Hardman Oy",
      "name": "Yvonne Stone",
      "notes": "asked for a one-pager",
      "outcome": "reply",
      "ts": "2026-06-11T08:34:00"
    },
    {
      "channel": "call",
      "company": "Wonka Oy",
      "name": "Mallory Hill",
      "notes": "interested but needs the board",
      "outcome": "conversation",
      "ts": "2026-06-11T08:37:00"
    },
    {
      "channel": "call",
      "company": "Pierce Oy",
      "name": "Olivia Marsh",
      "notes": "no budget this year",
      "outcome": "declined",
      "ts": "2026-06-11T12:43:00"
    },
    {
      "channel": "call",
      "company": "Pearson Oy",
      "name": "Niaj Frost",
      "notes": null,
      "outcome": "no_answer",
      "ts": "2026-06-11T12:56:00"
    },
    {
      "channel": "email",
      "company": "Oscorp O\u00dc",
      "name": "Hank Brooks",
      "notes": "asked for a one-pager",
      "outcome": "reply",
      "ts": "2026-06-11T17:29:00"
    },
    {
      "channel": "email",
      "company": "Aperture Oy",
      "name": "Victor Hill",
      "notes": "asked for a one-pager",
      "outcome": "reply",
      "ts": "2026-06-11T18:45:00"
    }
  ]
}

# Query 1: who to call, window 0800


## Aito calls

request:  {"from": "contacts", "limit": 10000}
response: total=50 (rows omitted)
request:  {"from": "touches", "limit": 10000}
response: total=150 (rows omitted)
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "operating", "contact_id.segment": "analytics", "contact_id.tier": "A", "days_since_prev_touch": "8-21", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.22890538964076834, "$value": "no_answer"}, {"$p": 0.20339335629072253, "$value": "meeting_booked"}, {"$p": 0.19619741817606853, "$value": "reply"}, {"$p": 0.14713271554276358, "$value": "no_reply"}, {"$p": 0.13982421170861956, "$value": "conversation"}, {"$p": 0.038844757892025315, "$value": "callback_requested"}, {"$p": 0.0313737774728926, "$value": "declined"}, {"$p": 0.014328373276139722, "$value": "bounced"}], "offset": 0, "total": 8}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "operating", "contact_id.segment": "ecommerce", "contact_id.tier": "C", "days_since_prev_touch": "22+", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.26255609857993484, "$value": "no_answer"}, {"$p": 0.19352079663160335, "$value": "conversation"}, {"$p": 0.19016846189961764, "$value": "reply"}, {"$p": 0.12425636371243823, "$value": "no_reply"}, {"$p": 0.11188613759209802, "$value": "meeting_booked"}, {"$p": 0.049356059708327106, "$value": "declined"}, {"$p": 0.03593818237895962, "$value": "callback_requested"}, {"$p": 0.03231789949702096, "$value": "bounced"}], "offset": 0, "total": 8}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "announced", "contact_id.segment": "ecommerce", "contact_id.tier": "C", "days_since_prev_touch": "8-21", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.34125992814286543, "$value": "no_reply"}, {"$p": 0.22988073514435697, "$value": "no_answer"}, {"$p": 0.18777846877088716, "$value": "conversation"}, {"$p": 0.07018108138628316, "$value": "meeting_booked"}, {"$p": 0.05667072945934596, "$value": "declined"}, {"$p": 0.05468307578925952, "$value": "reply"}, {"$p": 0.04080177805670337, "$value": "callback_requested"}, {"$p": 0.018744203250298446, "$value": "bounced"}], "offset": 0, "total": 8}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "shipped", "contact_id.segment": "other", "contact_id.tier": "C", "days_since_prev_touch": "8-21", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.530672634483406, "$value": "no_answer"}, {"$p": 0.21841147704487793, "$value": "conversation"}, {"$p": 0.09328286441752782, "$value": "no_reply"}, {"$p": 0.061381746569389, "$value": "reply"}, {"$p": 0.04857012809607344, "$value": "meeting_booked"}, {"$p": 0.029606034659720774, "$value": "declined"}, {"$p": 0.011401572647385824, "$value": "callback_requested"}, {"$p": 0.006673542081619418, "$value": "bounced"}], "offset": 0, "total": 8}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "announced", "contact_id.segment": "erp", "contact_id.tier": "A", "days_since_prev_touch": "8-21", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.3255353949096589, "$value": "no_reply"}, {"$p": 0.23321144484326162, "$value": "no_answer"}, {"$p": 0.11445979459351767, "$value": "meeting_booked"}, {"$p": 0.11186019268040862, "$value": "conversation"}, {"$p": 0.10577968983712031, "$value": "reply"}, {"$p": 0.05125639199930672, "$value": "declined"}, {"$p": 0.04194939951245892, "$value": "callback_requested"}, {"$p": 0.01594769162426735, "$value": "bounced"}], "offset": 0, "total": 8}

## Derived

[
  {
    "$p": 0.3820623258913674,
    "company": "Sterling BV",
    "contact_id": "sc014",
    "name": "Eve Fields",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "operating",
      "days_since_prev_touch": "8-21",
      "segment": "analytics",
      "tier": "A",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.341345116602661,
    "company": "Encom O\u00dc",
    "contact_id": "sc021",
    "name": "Victor Vale",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "operating",
      "days_since_prev_touch": "22+",
      "segment": "ecommerce",
      "tier": "C",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.2987613282138737,
    "company": "Omni Oy",
    "contact_id": "sc015",
    "name": "Carol Gray",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "announced",
      "days_since_prev_touch": "8-21",
      "segment": "ecommerce",
      "tier": "C",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.2783831777883372,
    "company": "Bluth Oy",
    "contact_id": "sc049",
    "name": "Mona Hill",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "shipped",
      "days_since_prev_touch": "8-21",
      "segment": "other",
      "tier": "C",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.26826938678638523,
    "company": "Pied BV",
    "contact_id": "sc002",
    "name": "Judy Lake",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "announced",
      "days_since_prev_touch": "8-21",
      "segment": "erp",
      "tier": "A",
      "weekday": "fri",
      "window": "0800"
    }
  }
]

# Query 2: opener context for sc001


## Aito calls

request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "sc001"}}
response: total=1 (rows omitted)
request:  {"from": "touches", "limit": 1000, "where": {"contact_id": {"$not": "sc001"}, "outcome": {"$or": ["conversation", "meeting_booked"]}}}
response: total=23 (rows omitted)
request:  {"from": "contacts", "limit": 1000, "select": ["contact_id", "name", "company", "segment", "tier", "ai_lifecycle"], "where": {"contact_id": {"$or": ["sc002", "sc003", "sc006", "sc010", "sc013", "sc014", "sc018", "sc021", "sc025", "sc028", "sc029", "sc034", "sc037", "sc038", "sc044", "sc050"]}, "segment": "consultancy"}}
response: total=1 (rows omitted)

## Derived

[
  {
    "ai_lifecycle": "announced",
    "company": "Globex Oy",
    "evidence": {
      "channel": "call",
      "notes": "walked through the idea, wants material",
      "outcome": "conversation",
      "ts": "2026-05-08T17:11:00",
      "window": "1600"
    },
    "segment": "consultancy",
    "similar_contact": "Frank Banks",
    "tier": "B"
  }
]
