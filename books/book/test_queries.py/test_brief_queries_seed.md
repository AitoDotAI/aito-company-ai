# Query 3: what changed


## Aito calls

request:  {"from": "touches", "limit": 100, "where": {"ts": {"$gte": "2026-06-11T00:00:00"}}}
response: total=6 (rows omitted)
request:  {"from": "touches", "limit": 100, "where": {"next_action_due": {"$gt": "", "$lte": "2026-06-15"}}}
response: total=54 (rows omitted)

## Derived

{
  "follow_ups_due": [
    {
      "company": "Rekall BV",
      "contact_id": "sc060",
      "due": "2026-04-17",
      "name": "Frank Knight",
      "next_action": "send one-pager"
    },
    {
      "company": "Pendant Oy",
      "contact_id": "sc013",
      "due": "2026-04-21",
      "name": "Grace Ford",
      "next_action": "send pricing summary"
    },
    {
      "company": "Nakatomi O\u00dc",
      "contact_id": "sc016",
      "due": "2026-05-01",
      "name": "Grace Lane",
      "next_action": "send one-pager"
    },
    {
      "company": "Sirius Oy",
      "contact_id": "sc045",
      "due": "2026-05-08",
      "name": "Mallory Wells",
      "next_action": "prepare demo"
    },
    {
      "company": "Vance BV",
      "contact_id": "sc024",
      "due": "2026-05-12",
      "name": "Zara Day",
      "next_action": "send pricing summary"
    },
    {
      "company": "Tyrell Oy",
      "contact_id": "sc001",
      "due": "2026-05-28",
      "name": "Alice Hill",
      "next_action": "send one-pager"
    },
    {
      "company": "Vertex GmbH",
      "contact_id": "sc049",
      "due": "2026-05-29",
      "name": "Zara Cross",
      "next_action": "send one-pager"
    },
    {
      "company": "Delos Ab",
      "contact_id": "sc022",
      "due": "2026-06-01",
      "name": "Yvonne Knight",
      "next_action": "send one-pager"
    },
    {
      "company": "Nimbus O\u00dc",
      "contact_id": "sc015",
      "due": "2026-06-02",
      "name": "Olivia Gray",
      "next_action": "send one-pager"
    },
    {
      "company": "Slate O\u00dc",
      "contact_id": "sc040",
      "due": "2026-06-05",
      "name": "Heidi Marsh",
      "next_action": "send pricing summary"
    },
    {
      "company": "Sterling Oy",
      "contact_id": "sc044",
      "due": "2026-06-05",
      "name": "Mallory Frost",
      "next_action": "call back"
    },
    {
      "company": "Lumon Oy",
      "contact_id": "sc018",
      "due": "2026-06-07",
      "name": "Bob Wells",
      "next_action": "send one-pager"
    },
    {
      "company": "Slate O\u00dc",
      "contact_id": "sc059",
      "due": "2026-06-07",
      "name": "Peggy Fields",
      "next_action": "send one-pager"
    },
    {
      "company": "Pied Oy",
      "contact_id": "sc038",
      "due": "2026-06-07",
      "name": "Victor Brooks",
      "next_action": "send one-pager"
    },
    {
      "company": "Omni O\u00dc",
      "contact_id": "sc023",
      "due": "2026-06-11",
      "name": "Olivia Snow",
      "next_action": "send one-pager"
    },
    {
      "company": "Spectre Oy",
      "contact_id": "sc035",
      "due": "2026-06-12",
      "name": "Judy Banks",
      "next_action": "send one-pager"
    },
    {
      "company": "Slate O\u00dc",
      "contact_id": "sc019",
      "due": "2026-06-12",
      "name": "Eve Knight",
      "next_action": "send one-pager"
    },
    {
      "company": "Duff O\u00dc",
      "contact_id": "sc042",
      "due": "2026-06-13",
      "name": "Mallory Reed",
      "next_action": "send one-pager"
    }
  ],
  "since_yesterday": [
    {
      "channel": "call",
      "company": "Initech Oy",
      "name": "Zara Knight",
      "notes": null,
      "outcome": "no_answer",
      "ts": "2026-06-11T08:27:00"
    },
    {
      "channel": "linkedin",
      "company": "Onyx Oy",
      "name": "Frank Pike",
      "notes": null,
      "outcome": "no_reply",
      "ts": "2026-06-11T08:46:00"
    },
    {
      "channel": "call",
      "company": "Nimbus O\u00dc",
      "name": "Bob Banks",
      "notes": null,
      "outcome": "no_answer",
      "ts": "2026-06-11T09:23:00"
    },
    {
      "channel": "email",
      "company": "Duff O\u00dc",
      "name": "Mallory Reed",
      "notes": "asked for a one-pager",
      "outcome": "reply",
      "ts": "2026-06-11T16:19:00"
    },
    {
      "channel": "linkedin",
      "company": "Spectre Oy",
      "name": "Judy Banks",
      "notes": "asked for a one-pager",
      "outcome": "reply",
      "ts": "2026-06-11T17:29:00"
    },
    {
      "channel": "linkedin",
      "company": "Spectre Oy",
      "name": "Judy Banks",
      "notes": null,
      "outcome": "no_reply",
      "ts": "2026-06-11T18:45:00"
    }
  ]
}

# Query 1: who to call, window 0800


## Aito calls

request:  {"from": "contacts", "limit": 5000, "offset": 0, "select": ["contact_id", "name", "company", "phone_present", "segment", "tier", "ai_lifecycle"]}
response: total=60 (rows omitted)
request:  {"from": "touches", "limit": 5000, "offset": 0, "select": ["contact_id", "ts", "next_action_due"]}
response: total=150 (rows omitted)
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "operating", "contact_id.segment": "consultancy", "contact_id.tier": "B", "days_since_prev_touch": "22+", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.2847605803118647, "$value": "no_answer"}, {"$p": 0.2428641731590634, "$value": "conversation"}, {"$p": 0.20704986620534288, "$value": "reply"}, {"$p": 0.11263760762869192, "$value": "no_reply"}, {"$p": 0.06564519515984141, "$value": "bounced"}, {"$p": 0.05411700351897197, "$value": "meeting_booked"}, {"$p": 0.01909606757780468, "$value": "declined"}, {"$p": 0.013829506438419042, "$value": "callback_requested"}], "kind": "rows", "offset": 0, "total": 8}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "none", "contact_id.segment": "ecommerce", "contact_id.tier": "B", "days_since_prev_touch": "first", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.3263576932693491, "$value": "no_answer"}, {"$p": 0.2427565282691741, "$value": "conversation"}, {"$p": 0.1902865008168446, "$value": "no_reply"}, {"$p": 0.12110646070849156, "$value": "reply"}, {"$p": 0.06961799073685548, "$value": "declined"}, {"$p": 0.03948081801085559, "$value": "bounced"}, {"$p": 0.007700579599800943, "$value": "callback_requested"}, {"$p": 0.002693428588628675, "$value": "meeting_booked"}], "kind": "rows", "offset": 0, "total": 8}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "operating", "contact_id.segment": "erp", "contact_id.tier": "A", "days_since_prev_touch": "22+", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.3681929679462948, "$value": "no_reply"}, {"$p": 0.20347537394658305, "$value": "reply"}, {"$p": 0.1750090668426739, "$value": "conversation"}, {"$p": 0.16705305990433997, "$value": "no_answer"}, {"$p": 0.03172912284106878, "$value": "meeting_booked"}, {"$p": 0.027285835561911928, "$value": "callback_requested"}, {"$p": 0.022110905255566676, "$value": "bounced"}, {"$p": 0.005143667701560892, "$value": "declined"}], "kind": "rows", "offset": 0, "total": 8}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "operating", "contact_id.segment": "analytics", "contact_id.tier": "B", "days_since_prev_touch": "22+", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.3496706950691187, "$value": "no_reply"}, {"$p": 0.24518559375839064, "$value": "no_answer"}, {"$p": 0.18106435880935856, "$value": "conversation"}, {"$p": 0.1116585440414892, "$value": "reply"}, {"$p": 0.053968738101086475, "$value": "bounced"}, {"$p": 0.02493968385293493, "$value": "declined"}, {"$p": 0.02306457696092509, "$value": "meeting_booked"}, {"$p": 0.010447809406696519, "$value": "callback_requested"}], "kind": "rows", "offset": 0, "total": 8}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "operating", "contact_id.segment": "accounting", "contact_id.tier": "B", "days_since_prev_touch": "8-21", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.34370995592956455, "$value": "reply"}, {"$p": 0.2458117436958566, "$value": "no_reply"}, {"$p": 0.18155905838000005, "$value": "no_answer"}, {"$p": 0.13376331272966768, "$value": "conversation"}, {"$p": 0.0568040816786566, "$value": "meeting_booked"}, {"$p": 0.0220874328348783, "$value": "declined"}, {"$p": 0.011919686612060918, "$value": "bounced"}, {"$p": 0.004344728139315302, "$value": "callback_requested"}], "kind": "rows", "offset": 0, "total": 8}

## Derived

[
  {
    "$p": 0.31081068311645443,
    "company": "Vance BV",
    "contact_id": "sc024",
    "name": "Zara Day",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "operating",
      "days_since_prev_touch": "22+",
      "segment": "consultancy",
      "tier": "B",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.2531505364576037,
    "company": "Wayne O\u00dc",
    "contact_id": "sc011",
    "name": "Zara Pike",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "none",
      "days_since_prev_touch": "first",
      "segment": "ecommerce",
      "tier": "B",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.2340240252456546,
    "company": "Nakatomi O\u00dc",
    "contact_id": "sc016",
    "name": "Grace Lane",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "operating",
      "days_since_prev_touch": "22+",
      "segment": "erp",
      "tier": "A",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.21457674517698017,
    "company": "Wonka Oy",
    "contact_id": "sc037",
    "name": "Grace Marsh",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "operating",
      "days_since_prev_touch": "22+",
      "segment": "analytics",
      "tier": "B",
      "weekday": "fri",
      "window": "0800"
    }
  },
  {
    "$p": 0.1949121225476396,
    "company": "Pied Oy",
    "contact_id": "sc038",
    "name": "Victor Brooks",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "operating",
      "days_since_prev_touch": "8-21",
      "segment": "accounting",
      "tier": "B",
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
response: total=16 (rows omitted)
request:  {"from": "contacts", "limit": 1000, "select": ["contact_id", "name", "company", "segment", "tier", "ai_lifecycle"], "where": {"contact_id": {"$or": ["sc006", "sc013", "sc016", "sc020", "sc024", "sc032", "sc037", "sc040", "sc042", "sc043", "sc045", "sc049"]}, "segment": "erp"}}
response: total=3 (rows omitted)

## Derived

[
  {
    "ai_lifecycle": "operating",
    "company": "Duff O\u00dc",
    "evidence": {
      "channel": "call",
      "notes": "agreed to a 30min walkthrough",
      "outcome": "meeting_booked",
      "ts": "2026-05-27T12:24:00",
      "window": "1215"
    },
    "segment": "erp",
    "similar_contact": "Mallory Reed",
    "tier": "B"
  },
  {
    "ai_lifecycle": "none",
    "company": "Nakatomi O\u00dc",
    "evidence": {
      "channel": "call",
      "notes": "good chat, asked about pricing",
      "outcome": "conversation",
      "ts": "2026-05-15T17:02:00",
      "window": "1600"
    },
    "segment": "erp",
    "similar_contact": "Peggy Rivers",
    "tier": "A"
  },
  {
    "ai_lifecycle": "operating",
    "company": "Nakatomi O\u00dc",
    "evidence": {
      "channel": "call",
      "notes": "agreed to a 30min walkthrough",
      "outcome": "meeting_booked",
      "ts": "2026-04-27T16:50:00",
      "window": "1600"
    },
    "segment": "erp",
    "similar_contact": "Grace Lane",
    "tier": "A"
  }
]
