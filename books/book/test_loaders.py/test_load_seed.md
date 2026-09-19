# Loader gate: data/seed


## Schema


## Load

contacts:    rows in file = rows in Aito = 50
touches:     rows in file = rows in Aito = 150
sessions:    rows in file = rows in Aito = 600
materials:   rows in file = rows in Aito = 40
channels:    rows in file = rows in Aito = 5
posts:       rows in file = rows in Aito = 120
todos:       rows in file = rows in Aito = 102
deals:       rows in file = rows in Aito = 80
decisions:   rows in file = rows in Aito = 60
experiments: rows in file = rows in Aito = 90
events:      rows in file = rows in Aito = 14
routines:    rows in file = rows in Aito = 7

## Sample rows: contacts

request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "sc001"}}
response: {"ai_lifecycle": "none", "company": "Genco Oy", "company_id": "genco-oy", "contact_id": "sc001", "country": "Finland", "created": "2025-07-14", "email_present": false, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": true, "name": "Carol Lane", "notes_tags": "met-at-event spreadsheet-heavy", "phone_present": false, "role": "Partner", "search_text": "Carol Lane Genco Oy Partner consultancy met-at-event spreadsheet-heavy", "search_title": "Carol Lane", "segment": "consultancy", "source": "cold", "tier": "A"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "sc002"}}
response: {"ai_lifecycle": "announced", "company": "Pied BV", "company_id": "pied-bv", "contact_id": "sc002", "country": "Netherlands", "created": "2026-01-24", "email_present": true, "ever_conversation": true, "ever_meeting": false, "ever_reached": true, "ever_touched": true, "name": "Judy Lake", "notes_tags": "founder-led met-at-event", "phone_present": true, "role": "CFO", "search_text": "Judy Lake Pied BV CFO erp founder-led met-at-event", "search_title": "Judy Lake", "segment": "erp", "source": "cold", "tier": "A"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "sc003"}}
response: {"ai_lifecycle": "operating", "company": "Wonka Oy", "company_id": "wonka-oy", "contact_id": "sc003", "country": "Finland", "created": "2026-02-09", "email_present": true, "ever_conversation": true, "ever_meeting": true, "ever_reached": true, "ever_touched": true, "name": "Mallory Hill", "notes_tags": "", "phone_present": true, "role": "CTO", "search_text": "Mallory Hill Wonka Oy CTO other", "search_title": "Mallory Hill", "segment": "other", "source": "trigger", "tier": "A"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "sc004"}}
response: {"ai_lifecycle": "announced", "company": "Soylent Oy", "company_id": "soylent-oy", "contact_id": "sc004", "country": "Finland", "created": "2026-05-11", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": false, "name": "Zara Snow", "notes_tags": "multi-entity slow-cycle", "phone_present": true, "role": "COO", "search_text": "Zara Snow Soylent Oy COO erp multi-entity slow-cycle", "search_title": "Zara Snow", "segment": "erp", "source": "cold", "tier": "C"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "sc005"}}
response: {"ai_lifecycle": "none", "company": "Nakatomi GmbH", "company_id": "nakatomi-gmbh", "contact_id": "sc005", "country": "Germany", "created": "2025-06-30", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": true, "name": "Bob Snow", "notes_tags": "inbound", "phone_present": false, "role": "Partner", "search_text": "Bob Snow Nakatomi GmbH Partner ecommerce inbound", "search_title": "Bob Snow", "segment": "ecommerce", "source": "referral", "tier": "B"}

## Sample rows: touches

request:  {"from": "touches", "limit": 1, "where": {"touch_id": "st101"}}
response: {"booked": false, "channel": "call", "contact_id": "sc010", "days_since_prev_touch": "first", "good_outcome": false, "outcome": "no_answer", "reached": false, "touch_id": "st101", "ts": "2026-04-03T08:49:00", "weekday": "fri", "window": "0800"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "st017"}}
response: {"booked": false, "channel": "email", "contact_id": "sc028", "days_since_prev_touch": "first", "good_outcome": false, "outcome": "no_reply", "reached": false, "touch_id": "st017", "ts": "2026-04-03T09:14:00", "weekday": "fri", "window": "0800"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "st021"}}
response: {"booked": false, "channel": "email", "contact_id": "sc003", "days_since_prev_touch": "first", "good_outcome": false, "notes": "replied, lukewarm but open", "outcome": "reply", "reached": true, "touch_id": "st021", "ts": "2026-04-03T12:38:00", "weekday": "fri", "window": "1215"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "st011"}}
response: {"booked": false, "channel": "email", "contact_id": "sc039", "days_since_prev_touch": "first", "good_outcome": false, "notes": "asked for a one-pager", "outcome": "reply", "reached": true, "touch_id": "st011", "ts": "2026-04-06T14:00:00", "weekday": "mon", "window": "other"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "st081"}}
response: {"booked": false, "channel": "call", "contact_id": "sc020", "days_since_prev_touch": "first", "good_outcome": false, "notes": "happy with current setup", "outcome": "declined", "reached": true, "touch_id": "st081", "ts": "2026-04-06T17:23:00", "weekday": "mon", "window": "1600"}

## Sample rows: sessions

request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ss0001"}}
response: {"converted_paid": false, "country": "Germany", "device": "tablet", "landing_page": "/blog", "session_id": "ss0001", "signed_up": false, "source": "direct", "started_trial": false, "ts": "2026-02-12"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ss0081"}}
response: {"campaign": "retargeting", "converted_paid": true, "country": "Finland", "device": "mobile", "landing_page": "/pricing", "session_id": "ss0081", "signed_up": true, "source": "paid_search", "started_trial": true, "ts": "2026-02-12"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ss0136"}}
response: {"campaign": "spring_launch", "converted_paid": false, "country": "Germany", "device": "desktop", "landing_page": "/", "session_id": "ss0136", "signed_up": false, "source": "paid_search", "started_trial": false, "ts": "2026-02-12"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ss0201"}}
response: {"campaign": "brand_terms", "converted_paid": false, "country": "Finland", "device": "mobile", "landing_page": "/docs", "session_id": "ss0201", "signed_up": false, "source": "paid_search", "started_trial": false, "ts": "2026-02-12"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ss0288"}}
response: {"converted_paid": false, "country": "Sweden", "device": "tablet", "landing_page": "/blog", "session_id": "ss0288", "signed_up": false, "source": "organic", "started_trial": false, "ts": "2026-02-12"}

## Sample rows: materials

request:  {"from": "materials", "limit": 1, "where": {"material_id": "sm001"}}
response: {"ai_made": "manual", "created": "2026-01-29", "lane": "warm", "length_chars": 680, "material_id": "sm001", "title": "oss tool notes", "topic": "oss_tool", "type": "blog"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "sm002"}}
response: {"ai_made": "ai-assisted", "created": "2026-06-06", "lane": "warm", "length_chars": 120, "material_id": "sm002", "title": "positioning teardown", "topic": "positioning", "type": "thread"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "sm003"}}
response: {"ai_made": "ai-assisted", "created": "2026-03-11", "lane": "warm", "length_chars": 320, "material_id": "sm003", "title": "core product story", "topic": "core_product", "type": "talk"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "sm004"}}
response: {"ai_made": "ai-assisted", "created": "2026-06-06", "lane": "cold", "length_chars": 320, "material_id": "sm004", "title": "product story", "topic": "product", "type": "whitepaper"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "sm005"}}
response: {"ai_made": "ai-assisted", "created": "2026-03-10", "lane": "warm", "length_chars": 680, "material_id": "sm005", "title": "oss tool guide", "topic": "oss_tool", "type": "whitepaper"}

## Sample rows: channels

request:  {"from": "channels", "limit": 1, "where": {"channel_id": "sk01"}}
response: {"channel_id": "sk01", "created": "2025-05-08", "name": "Hacker News", "platform": "hackernews"}
request:  {"from": "channels", "limit": 1, "where": {"channel_id": "sk02"}}
response: {"channel_id": "sk02", "created": "2025-05-08", "name": "r/programming", "platform": "reddit"}
request:  {"from": "channels", "limit": 1, "where": {"channel_id": "sk03"}}
response: {"channel_id": "sk03", "created": "2025-05-08", "name": "r/Python", "platform": "reddit"}
request:  {"from": "channels", "limit": 1, "where": {"channel_id": "sk04"}}
response: {"channel_id": "sk04", "created": "2025-05-08", "name": "LinkedIn", "platform": "linkedin"}
request:  {"from": "channels", "limit": 1, "where": {"channel_id": "sk05"}}
response: {"channel_id": "sk05", "created": "2025-05-08", "name": "Company blog", "platform": "blog"}

## Sample rows: posts

request:  {"from": "posts", "limit": 1, "where": {"post_id": "sp0067"}}
response: {"ai_made": "ai", "channel_id": "sk02", "format": "text", "lane": "warm", "length_bucket": "long", "length_chars": 540, "link_placement": "n_a", "material_id": "sm006", "outcome": "flop", "platform": "reddit", "post_id": "sp0067", "posted_at": "2026-02-15", "reach_or_views": 70, "status": "posted", "tone": "announce", "topic": "product", "trials": 0, "upvotes": 1, "weekday": "sun", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "sp0042"}}
response: {"ai_made": "manual", "channel_id": "sk03", "format": "text", "lane": "cold", "length_bucket": "short", "length_chars": 240, "link_placement": "n_a", "material_id": "sm029", "outcome": "modest", "platform": "reddit", "post_id": "sp0042", "posted_at": "2026-02-16", "reach_or_views": 294, "status": "posted", "tone": "announce", "topic": "agent_inference", "trials": 0, "upvotes": 3, "weekday": "mon", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "sp0005"}}
response: {"ai_made": "ai-assisted", "channel_id": "sk03", "format": "link", "lane": "warm", "length_bucket": "short", "length_chars": 120, "link_placement": "n_a", "material_id": "sm002", "outcome": "modest", "platform": "reddit", "post_id": "sp0005", "posted_at": "2026-02-17", "reach_or_views": 609, "status": "posted", "tone": "builder", "topic": "positioning", "trials": 0, "upvotes": 6, "weekday": "tue", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "sp0007"}}
response: {"ai_made": "manual", "channel_id": "sk02", "format": "link", "lane": "cold", "length_bucket": "medium", "length_chars": 320, "link_placement": "n_a", "material_id": "sm011", "outcome": "modest", "platform": "reddit", "post_id": "sp0007", "posted_at": "2026-02-18", "reach_or_views": 469, "status": "posted", "tone": "builder", "topic": "product", "trials": 0, "upvotes": 10, "weekday": "wed", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "sp0047"}}
response: {"ai_made": "manual", "channel_id": "sk02", "format": "text", "lane": "warm", "length_bucket": "medium", "length_chars": 420, "link_placement": "n_a", "material_id": "sm027", "outcome": "modest", "platform": "reddit", "post_id": "sp0047", "posted_at": "2026-02-18", "reach_or_views": 271, "status": "posted", "tone": "announce", "topic": "customer_proof", "trials": 0, "upvotes": 3, "weekday": "wed", "won": false}

## Sample rows: todos

request:  {"from": "todos", "limit": 1, "where": {"todo_id": "sd017"}}
response: {"action_type": "research", "area": "experiments", "linked_type": "workstream", "prep_status": "in_progress", "priority": 3, "status": "ready", "title": "Review the customer-proof cohort", "todo_id": "sd017"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "sd004"}}
response: {"action_type": "post", "area": "marketing", "due_date": "2026-06-12", "linked_type": "asset", "prep_status": "prep_needed", "priority": 1, "slot": "09:00", "status": "ready", "title": "Ship the customer-proof post", "todo_id": "sd004", "window": "mon_0800"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "sd005"}}
response: {"action_type": "post", "area": "marketing", "due_date": "2026-06-11", "linked_type": "asset", "prep_status": "prep_needed", "priority": 1, "slot": "15:30", "status": "ready", "title": "Draft the customer-proof narrative", "todo_id": "sd005", "window": "tue_0800"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "sd010"}}
response: {"action_type": "post", "area": "marketing", "due_date": "2026-06-18", "linked_type": "asset", "prep_status": "prep_needed", "priority": 1, "slot": "14:30", "status": "ready", "title": "Propagate the agent-inference demo", "todo_id": "sd010", "window": "fri_1430"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "sd015"}}
response: {"action_type": "post", "area": "marketing", "due_date": "2026-06-22", "linked_type": "asset", "prep_status": "ready", "priority": 2, "slot": "15:30", "status": "draft", "title": "Propagate the positioning demo", "todo_id": "sd015", "window": "fri_1430"}

## Sample rows: deals

request:  {"from": "deals", "limit": 1, "where": {"deal_id": "sec003"}}
response: {"blocker": "no_champion", "champion_present": false, "company": "Abstergo Oy", "company_id": "abstergo-oy", "created": "2025-11-08", "deal_id": "sec003", "last_touch_date": "2025-12-28", "probability": 40, "search_text": "Abstergo Oy ecommerce closed_lost no_champion", "search_title": "Abstergo Oy", "segment": "ecommerce", "stage": "closed_lost", "value_eur": 80000, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "sec004"}}
response: {"blocker": "no_champion", "champion_present": false, "company": "Abstergo Oy", "company_id": "abstergo-oy", "created": "2025-11-25", "deal_id": "sec004", "last_touch_date": "2026-02-16", "probability": 20, "search_text": "Abstergo Oy accounting closed_lost no_champion", "search_title": "Abstergo Oy", "segment": "accounting", "stage": "closed_lost", "value_eur": 80000, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "sec005"}}
response: {"blocker": "no_champion", "champion_present": false, "company": "Raviga Oy", "company_id": "raviga-oy", "created": "2025-05-12", "deal_id": "sec005", "last_touch_date": "2025-08-21", "probability": 50, "search_text": "Raviga Oy accounting closed_lost no_champion", "search_title": "Raviga Oy", "segment": "accounting", "stage": "closed_lost", "value_eur": 45000, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "sec007"}}
response: {"blocker": "none", "champion_present": false, "company": "Widmore Oy", "company_id": "widmore-oy", "created": "2025-04-23", "deal_id": "sec007", "last_touch_date": "2025-06-16", "probability": 60, "search_text": "Widmore Oy ecommerce closed_lost none", "search_title": "Widmore Oy", "segment": "ecommerce", "stage": "closed_lost", "value_eur": 15000, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "sec008"}}
response: {"blocker": "timing_mismatch", "champion_present": false, "company": "Cobalt Oy", "company_id": "cobalt-oy", "created": "2025-06-26", "deal_id": "sec008", "last_touch_date": "2026-02-27", "probability": 60, "search_text": "Cobalt Oy accounting closed_lost timing_mismatch", "search_title": "Cobalt Oy", "segment": "accounting", "stage": "closed_lost", "value_eur": 80000, "won": false}

## Sample rows: decisions

request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "sx031"}}
response: {"accepted": false, "agent_confidence": 0.63, "chosen": "sc003", "confidence_bucket": "medium", "context_ai_lifecycle": "operating", "context_segment": "other", "context_tier": "A", "context_weekday": "wed", "context_window": "0800", "decision_id": "sx031", "decision_type": "followup_timing", "human_action": "ignored", "ts": "2026-03-15T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "sx020"}}
response: {"accepted": true, "agent_confidence": 0.92, "chosen": "sc016", "confidence_bucket": "high", "context_ai_lifecycle": "shipped", "context_segment": "ecommerce", "context_tier": "C", "context_weekday": "tue", "context_window": "1600", "decision_id": "sx020", "decision_type": "opener_choice", "human_action": "accepted", "outcome_after": "good", "ts": "2026-03-16T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "sx030"}}
response: {"accepted": true, "agent_confidence": 0.61, "chosen": "sc004", "confidence_bucket": "medium", "context_ai_lifecycle": "announced", "context_segment": "erp", "context_tier": "C", "context_weekday": "mon", "context_window": "1215", "decision_id": "sx030", "decision_type": "opener_choice", "human_action": "accepted", "outcome_after": "missed", "ts": "2026-03-16T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "sx027"}}
response: {"accepted": false, "agent_confidence": 0.3, "chosen": "sc049", "confidence_bucket": "low", "context_ai_lifecycle": "shipped", "context_segment": "other", "context_tier": "C", "context_weekday": "mon", "context_window": "0800", "decision_id": "sx027", "decision_type": "followup_timing", "human_action": "overridden", "human_alternative": "reordered", "ts": "2026-03-20T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "sx016"}}
response: {"accepted": true, "agent_confidence": 0.15, "chosen": "sc034", "confidence_bucket": "low", "context_ai_lifecycle": "shipped", "context_segment": "analytics", "context_tier": "A", "context_weekday": "mon", "context_window": "1215", "decision_id": "sx016", "decision_type": "opener_choice", "human_action": "accepted", "ts": "2026-03-24T08:10:00"}

## Sample rows: experiments

request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "sr060"}}
response: {"area": "referral", "baseline": 0.193, "created": "2026-01-13", "decided": "2026-01-22", "effort": "small", "experiment_id": "sr060", "hypothesis": "A pricing change lifts referral_rate from 0.193 to 0.243.", "learning": "referral_rate reached 0.308; shipped", "metric": "referral_rate", "result": 0.308, "started": "2026-01-13", "status": "validated", "target": 0.243, "type": "pricing", "validated": true}
request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "sr079"}}
response: {"area": "activation", "baseline": 0.095, "created": "2026-01-17", "decided": "2026-01-31", "effort": "medium", "experiment_id": "sr079", "hypothesis": "A feature change lifts trial_start_rate from 0.095 to 0.14.", "learning": "no lift over baseline; reverted", "metric": "trial_start_rate", "result": 0.097, "started": "2026-01-17", "status": "invalidated", "target": 0.14, "type": "feature", "validated": false}
request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "sr035"}}
response: {"area": "retention", "baseline": 0.228, "created": "2026-01-19", "decided": "2026-01-29", "effort": "large", "experiment_id": "sr035", "hypothesis": "A onboarding change lifts m1_retention from 0.228 to 0.321.", "learning": "no lift over baseline; reverted", "metric": "m1_retention", "result": 0.228, "started": "2026-01-19", "status": "invalidated", "target": 0.321, "type": "onboarding", "validated": false}
request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "sr014"}}
response: {"area": "activation", "baseline": 0.094, "created": "2026-01-20", "effort": "medium", "experiment_id": "sr014", "hypothesis": "A pricing change lifts trial_start_rate from 0.094 to 0.12.", "learning": "killed before a verdict", "metric": "trial_start_rate", "started": "2026-01-20", "status": "abandoned", "target": 0.12, "type": "pricing"}
request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "sr068"}}
response: {"area": "retention", "baseline": 0.082, "created": "2026-01-20", "decided": "2026-02-21", "effort": "small", "experiment_id": "sr068", "hypothesis": "A feature change lifts m1_retention from 0.082 to 0.119.", "learning": "m1_retention reached 0.159; shipped", "metric": "m1_retention", "result": 0.159, "started": "2026-01-20", "status": "validated", "target": 0.119, "type": "feature", "validated": true}

## Sample rows: events

request:  {"from": "events", "limit": 1, "where": {"event_id": "sv010"}}
response: {"cost_eur": 600, "created": "2026-05-16", "decided": "2026-04-26", "event_id": "sv010", "location": "Stockholm", "name": "DevMeetup 2026", "notes": "low fit for the cost", "starts": "2026-05-16", "status": "no_go", "type": "meetup"}
request:  {"from": "events", "limit": 1, "where": {"event_id": "sv014"}}
response: {"cost_eur": 0, "created": "2026-03-20", "event_id": "sv014", "location": "online", "name": "Indie Hackers 2026", "starts": "2026-05-25", "status": "candidate", "type": "meetup"}
request:  {"from": "events", "limit": 1, "where": {"event_id": "sv001"}}
response: {"cost_eur": 0, "created": "2026-04-18", "event_id": "sv001", "location": "Amsterdam", "name": "AI Summit 2026", "starts": "2026-06-22", "status": "candidate", "type": "conference"}
request:  {"from": "events", "limit": 1, "where": {"event_id": "sv004"}}
response: {"cost_eur": 0, "created": "2026-03-16", "decided": "2026-07-08", "event_id": "sv004", "location": "Berlin", "name": "PyData 2026", "notes": "worth a talk / booth", "starts": "2026-08-04", "status": "go", "type": "conference"}
request:  {"from": "events", "limit": 1, "where": {"event_id": "sv002"}}
response: {"cost_eur": 0, "created": "2026-03-22", "decided": "2026-07-24", "event_id": "sv002", "location": "online", "name": "ProductCon 2026", "notes": "worth a talk / booth", "starts": "2026-08-18", "status": "go", "type": "talk"}

## Sample rows: routines

request:  {"from": "routines", "limit": 1, "where": {"routine_id": "so01"}}
response: {"active": true, "area": "sales", "cadence": "weekly", "created": "2026-05-13", "notes": "next outbound batch", "prep": "prospects", "routine_id": "so01", "title": "Fill La Growth Machine", "weekday": "mon"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "so02"}}
response: {"active": true, "area": "operations", "cadence": "weekly", "created": "2026-05-13", "prep": "brief", "routine_id": "so02", "title": "Prepare the week", "weekday": "sun"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "so03"}}
response: {"active": true, "area": "operations", "cadence": "weekly", "created": "2026-05-13", "prep": "brief", "routine_id": "so03", "title": "Friday board review", "weekday": "fri"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "so04"}}
response: {"active": true, "area": "marketing", "cadence": "weekly", "created": "2026-05-13", "notes": "draft + schedule posts", "prep": "none", "routine_id": "so04", "title": "Weekly content batch", "weekday": "tue"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "so05"}}
response: {"active": true, "area": "sales", "cadence": "weekly", "created": "2026-05-13", "notes": "update stages, clear stale", "prep": "none", "routine_id": "so05", "title": "Pipeline hygiene", "weekday": "wed"}
