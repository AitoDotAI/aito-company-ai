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

request:  {"from": "contacts", "limit": 10000}
response: total=60 (rows omitted)
request:  {"from": "touches", "limit": 10000}
response: total=150 (rows omitted)
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "operating", "contact_id.segment": "consultancy", "contact_id.tier": "B", "days_since_prev_touch": "22+", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.24479018474387657, "$value": "no_answer"}, {"$p": 0.20877456335482436, "$value": "conversation"}, {"$p": 0.1779873286677982, "$value": "reply"}, {"$p": 0.15419515208604506, "$value": "no_reply"}, {"$p": 0.07739120891313322, "$value": "meeting_booked"}, {"$p": 0.07450742339570174, "$value": "bounced"}, {"$p": 0.035526872171888366, "$value": "declined"}, {"$p": 0.026827266666732543, "$value": "callback_requested"}], "offset": 0, "total": 8}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "none", "contact_id.segment": "ecommerce", "contact_id.tier": "B", "days_since_prev_touch": "first", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.31083285486402973, "$value": "no_answer"}, {"$p": 0.23120859803513838, "$value": "conversation"}, {"$p": 0.18123457026083026, "$value": "no_reply"}, {"$p": 0.11534542528289869, "$value": "reply"}, {"$p": 0.06630626229109554, "$value": "declined"}, {"$p": 0.050895442174332096, "$value": "bounced"}, {"$p": 0.02506224185833559, "$value": "callback_requested"}, {"$p": 0.019114605233339663, "$value": "meeting_booked"}], "offset": 0, "total": 8}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "operating", "contact_id.segment": "erp", "contact_id.tier": "A", "days_since_prev_touch": "22+", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.32507805903504616, "$value": "no_reply"}, {"$p": 0.17964867714049737, "$value": "reply"}, {"$p": 0.15451573689764053, "$value": "conversation"}, {"$p": 0.1474913678348392, "$value": "no_answer"}, {"$p": 0.06406965280988247, "$value": "bounced"}, {"$p": 0.05572912921651297, "$value": "callback_requested"}, {"$p": 0.04660301267960836, "$value": "meeting_booked"}, {"$p": 0.026864364385972846, "$value": "declined"}], "offset": 0, "total": 8}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "operating", "contact_id.segment": "analytics", "contact_id.tier": "B", "days_since_prev_touch": "22+", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.31906698741814404, "$value": "no_reply"}, {"$p": 0.2237265800708719, "$value": "no_answer"}, {"$p": 0.1652173325038872, "$value": "conversation"}, {"$p": 0.10188601952980902, "$value": "reply"}, {"$p": 0.07616635651537321, "$value": "bounced"}, {"$p": 0.05003107133341512, "$value": "declined"}, {"$p": 0.03870456390148211, "$value": "meeting_booked"}, {"$p": 0.025201088727017474, "$value": "callback_requested"}], "offset": 0, "total": 8}
request:  {"from": "touches", "limit": 8, "predict": "outcome", "where": {"contact_id.ai_lifecycle": "operating", "contact_id.segment": "erp", "contact_id.tier": "C", "days_since_prev_touch": "22+", "weekday": "fri", "window": "0800"}}
response: {"hits": [{"$p": 0.3638637087852734, "$value": "no_reply"}, {"$p": 0.20788136693469944, "$value": "no_answer"}, {"$p": 0.11655992059148684, "$value": "conversation"}, {"$p": 0.08278772333179141, "$value": "bounced"}, {"$p": 0.08004166869815897, "$value": "reply"}, {"$p": 0.06315115875914516, "$value": "callback_requested"}, {"$p": 0.04525193619072652, "$value": "declined"}, {"$p": 0.04046251670871833, "$value": "meeting_booked"}], "offset": 0, "total": 8}

## Derived

[
  {
    "$p": 0.3129930389346901,
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
    "$p": 0.2753854451268136,
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
    "$p": 0.25684787879376186,
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
    "$p": 0.2291229851323868,
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
    "$p": 0.22017359605935033,
    "company": "Nakatomi O\u00dc",
    "contact_id": "sc054",
    "name": "Carol Vale",
    "phone_present": true,
    "why": {
      "ai_lifecycle": "operating",
      "days_since_prev_touch": "22+",
      "segment": "erp",
      "tier": "C",
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
