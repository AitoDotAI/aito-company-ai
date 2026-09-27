# Loader gate: data/seed


## Schema


## Load

contacts:    rows in file = rows in Aito = 60
touches:     rows in file = rows in Aito = 150
sessions:    rows in file = rows in Aito = 600
materials:   rows in file = rows in Aito = 40
channels:    rows in file = rows in Aito = 5
posts:       rows in file = rows in Aito = 120
todos:       rows in file = rows in Aito = 102
deals:       rows in file = rows in Aito = 280
decisions:   rows in file = rows in Aito = 60
experiments: rows in file = rows in Aito = 90
events:      rows in file = rows in Aito = 14
routines:    rows in file = rows in Aito = 7

## Sample rows: contacts

request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "sc001"}}
response: {"ai_lifecycle": "operating", "company": "Tyrell Oy", "company_id": "tyrell-oy", "contact_id": "sc001", "country": "Finland", "created": "2025-08-02", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": true, "ever_touched": true, "name": "Alice Hill", "notes_tags": "founder-led podcast-listener rfp-soon", "phone_present": false, "role": "CEO", "search_text": "Alice Hill Tyrell Oy CEO erp founder-led podcast-listener rfp-soon", "search_title": "Alice Hill", "segment": "erp", "source": "trigger", "tier": "A"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "sc002"}}
response: {"ai_lifecycle": "none", "company": "Mooby Ab", "company_id": "mooby-ab", "contact_id": "sc002", "country": "Sweden", "created": "2025-06-04", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": false, "name": "Heidi Banks", "notes_tags": "podcast-listener spreadsheet-heavy", "phone_present": false, "role": "CFO", "search_text": "Heidi Banks Mooby Ab CFO accounting podcast-listener spreadsheet-heavy", "search_title": "Heidi Banks", "segment": "accounting", "source": "cold", "tier": "C"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "sc003"}}
response: {"ai_lifecycle": "operating", "company": "Genco Oy", "company_id": "genco-oy", "contact_id": "sc003", "country": "Finland", "created": "2025-12-18", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": false, "name": "Judy Frost", "notes_tags": "newsletter", "phone_present": false, "role": "CTO", "search_text": "Judy Frost Genco Oy CTO analytics newsletter", "search_title": "Judy Frost", "segment": "analytics", "source": "cold", "tier": "C"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "sc004"}}
response: {"ai_lifecycle": "operating", "company": "Onyx Oy", "company_id": "onyx-oy", "contact_id": "sc004", "country": "Finland", "created": "2025-11-09", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": true, "name": "Frank Pike", "notes_tags": "founder-led tech-savvy", "phone_present": true, "role": "IT Manager", "search_text": "Frank Pike Onyx Oy IT Manager analytics founder-led tech-savvy", "search_title": "Frank Pike", "segment": "analytics", "source": "cold", "tier": "B"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "sc005"}}
response: {"ai_lifecycle": "shipped", "company": "Dunder GmbH", "company_id": "dunder-gmbh", "contact_id": "sc005", "country": "Germany", "created": "2026-01-24", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": false, "name": "Quinn Rivers", "notes_tags": "tech-savvy", "phone_present": true, "role": "CTO", "search_text": "Quinn Rivers Dunder GmbH CTO accounting tech-savvy", "search_title": "Quinn Rivers", "segment": "accounting", "source": "warm", "tier": "B"}

## Sample rows: touches

request:  {"from": "touches", "limit": 1, "where": {"touch_id": "st004"}}
response: {"booked": false, "channel": "email", "contact_id": "sc029", "days_since_prev_touch": "first", "good_outcome": false, "notes": "replied, lukewarm but open", "outcome": "reply", "reached": true, "touch_id": "st004", "ts": "2026-04-03T12:38:00", "weekday": "fri", "window": "1215"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "st040"}}
response: {"booked": false, "channel": "linkedin", "contact_id": "sc015", "days_since_prev_touch": "first", "good_outcome": false, "next_action": "send one-pager", "next_action_due": "2026-04-07", "notes": "replied, lukewarm but open", "outcome": "reply", "reached": true, "touch_id": "st040", "ts": "2026-04-06T14:00:00", "weekday": "mon", "window": "other"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "st063"}}
response: {"booked": false, "channel": "email", "contact_id": "sc051", "days_since_prev_touch": "first", "good_outcome": false, "next_action": "send one-pager", "next_action_due": "2026-04-09", "notes": "replied, lukewarm but open", "outcome": "reply", "reached": true, "touch_id": "st063", "ts": "2026-04-06T17:23:00", "weekday": "mon", "window": "1600"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "st051"}}
response: {"booked": false, "channel": "email", "contact_id": "sc019", "days_since_prev_touch": "first", "good_outcome": false, "next_action": "send one-pager", "next_action_due": "2026-04-09", "notes": "replied, lukewarm but open", "outcome": "reply", "reached": true, "touch_id": "st051", "ts": "2026-04-07T08:41:00", "weekday": "tue", "window": "0800"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "st133"}}
response: {"booked": false, "channel": "linkedin", "contact_id": "sc020", "days_since_prev_touch": "first", "good_outcome": false, "outcome": "no_reply", "reached": false, "touch_id": "st133", "ts": "2026-04-07T08:52:00", "weekday": "tue", "window": "0800"}

## Sample rows: sessions

request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ss0060"}}
response: {"campaign": "retargeting", "converted_paid": true, "country": "Finland", "device": "mobile", "landing_page": "/pricing", "session_id": "ss0060", "signed_up": true, "source": "paid_search", "started_trial": true, "ts": "2026-02-12"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ss0115"}}
response: {"campaign": "spring_launch", "converted_paid": false, "country": "Germany", "device": "desktop", "landing_page": "/", "session_id": "ss0115", "signed_up": false, "source": "paid_search", "started_trial": false, "ts": "2026-02-12"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ss0180"}}
response: {"campaign": "brand_terms", "converted_paid": false, "country": "Finland", "device": "mobile", "landing_page": "/docs", "session_id": "ss0180", "signed_up": false, "source": "paid_search", "started_trial": false, "ts": "2026-02-12"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ss0267"}}
response: {"converted_paid": false, "country": "Sweden", "device": "tablet", "landing_page": "/blog", "session_id": "ss0267", "signed_up": false, "source": "organic", "started_trial": false, "ts": "2026-02-12"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ss0300"}}
response: {"campaign": "brand_terms", "converted_paid": false, "country": "Estonia", "device": "desktop", "landing_page": "/pricing", "session_id": "ss0300", "signed_up": false, "source": "paid_search", "started_trial": false, "ts": "2026-02-12"}

## Sample rows: materials

request:  {"from": "materials", "limit": 1, "where": {"material_id": "sm001"}}
response: {"ai_made": "manual", "created": "2026-01-04", "lane": "warm", "length_chars": 680, "material_id": "sm001", "title": "product notes", "topic": "product", "type": "note"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "sm002"}}
response: {"ai_made": "manual", "created": "2026-04-21", "lane": "warm", "length_chars": 180, "material_id": "sm002", "title": "customer proof deep dive", "topic": "customer_proof", "type": "whitepaper"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "sm003"}}
response: {"ai_made": "manual", "created": "2026-01-01", "lane": "warm", "length_chars": 240, "material_id": "sm003", "title": "oss tool benchmark", "topic": "oss_tool", "type": "blog"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "sm004"}}
response: {"ai_made": "ai", "created": "2026-02-23", "lane": "warm", "length_chars": 420, "material_id": "sm004", "title": "customer proof story", "topic": "customer_proof", "type": "note"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "sm005"}}
response: {"ai_made": "manual", "created": "2026-04-05", "lane": "warm", "length_chars": 420, "material_id": "sm005", "title": "customer proof guide", "topic": "customer_proof", "type": "whitepaper"}

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

request:  {"from": "posts", "limit": 1, "where": {"post_id": "sp0047"}}
response: {"ai_made": "ai-assisted", "channel_id": "sk04", "format": "link", "lane": "warm", "length_bucket": "short", "length_chars": 120, "link_placement": "body", "material_id": "sm008", "outcome": "flop", "platform": "linkedin", "post_id": "sp0047", "posted_at": "2026-02-13", "reach_or_views": 62, "status": "posted", "tone": "explainer", "topic": "positioning", "trials": 0, "upvotes": 0, "weekday": "fri", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "sp0052"}}
response: {"ai_made": "manual", "channel_id": "sk02", "format": "text", "lane": "warm", "length_bucket": "short", "length_chars": 180, "link_placement": "n_a", "material_id": "sm006", "outcome": "modest", "platform": "reddit", "post_id": "sp0052", "posted_at": "2026-02-15", "reach_or_views": 261, "status": "posted", "tone": "announce", "topic": "product", "trials": 0, "upvotes": 3, "weekday": "sun", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "sp0027"}}
response: {"ai_made": "manual", "channel_id": "sk03", "format": "text", "lane": "warm", "length_bucket": "short", "length_chars": 240, "link_placement": "n_a", "material_id": "sm029", "outcome": "modest", "platform": "reddit", "post_id": "sp0027", "posted_at": "2026-02-16", "reach_or_views": 294, "status": "posted", "tone": "announce", "topic": "customer_proof", "trials": 0, "upvotes": 3, "weekday": "mon", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "sp0112"}}
response: {"ai_made": "manual", "channel_id": "sk05", "format": "link", "lane": "warm", "length_bucket": "long", "length_chars": 680, "link_placement": "n_a", "material_id": "sm001", "outcome": "win", "platform": "blog", "post_id": "sp0112", "posted_at": "2026-02-16", "reach_or_views": 391, "status": "posted", "tone": "narrate", "topic": "product", "trials": 0, "upvotes": 6, "weekday": "mon", "won": true}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "sp0032"}}
response: {"ai_made": "ai-assisted", "channel_id": "sk02", "format": "text", "lane": "cold", "length_bucket": "short", "length_chars": 120, "link_placement": "n_a", "material_id": "sm027", "outcome": "flop", "platform": "reddit", "post_id": "sp0032", "posted_at": "2026-02-18", "reach_or_views": 207, "status": "posted", "tone": "announce", "topic": "agent_inference", "trials": 0, "upvotes": 2, "weekday": "wed", "won": false}

## Sample rows: todos

request:  {"from": "todos", "limit": 1, "where": {"todo_id": "sd022"}}
response: {"action_type": "research", "area": "experiments", "linked_type": "workstream", "prep_status": "prep_needed", "priority": 2, "rev": "rv-0", "revs": "rv-0", "status": "blocked", "title": "Decide go/kill on positioning", "todo_id": "sd022"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "sd016"}}
response: {"action_type": "research", "area": "experiments", "linked_type": "workstream", "prep_status": "prep_needed", "priority": 3, "rev": "rv-0", "revs": "rv-0", "status": "ready", "title": "Analyze the agent-inference test results", "todo_id": "sd016"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "sd011"}}
response: {"action_type": "post", "area": "marketing", "due_date": "2026-06-16", "linked_type": "asset", "prep_status": "ready", "priority": 1, "rev": "rv-0", "revs": "rv-0", "slot": "14:30", "status": "prog", "title": "Ship the customer-proof post", "todo_id": "sd011", "window": "fri_1430"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "sd003"}}
response: {"action_type": "post", "area": "marketing", "due_date": "2026-06-22", "linked_type": "asset", "prep_status": "in_progress", "priority": 2, "rev": "rv-0", "revs": "rv-0", "slot": "10:30", "status": "ready", "title": "Draft the product narrative", "todo_id": "sd003", "window": "mon_0800"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "sd014"}}
response: {"action_type": "post", "area": "marketing", "due_date": "2026-06-15", "linked_type": "asset", "prep_status": "in_progress", "priority": 2, "rev": "rv-0", "revs": "rv-0", "slot": "14:30", "status": "prog", "title": "Draft the agent-inference narrative", "todo_id": "sd014", "window": "fri_eve"}

## Sample rows: deals

request:  {"from": "deals", "limit": 1, "where": {"deal_id": "sec001"}}
response: {"blocker": "timing_mismatch", "champion_present": false, "company": "Vertex GmbH", "company_id": "vertex-gmbh", "created": "2025-04-15", "deal_id": "sec001", "last_touch_date": "2025-11-23", "probability": 60, "search_text": "Vertex GmbH ecommerce closed_lost timing_mismatch", "search_title": "Vertex GmbH", "segment": "ecommerce", "stage": "closed_lost", "value_eur": 80000, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "sec002"}}
response: {"blocker": "demo_readiness", "champion_present": true, "company": "Hanso GmbH", "company_id": "hanso-gmbh", "created": "2025-04-08", "deal_id": "sec002", "last_touch_date": "2026-01-27", "probability": 40, "search_text": "Hanso GmbH accounting closed_lost demo_readiness", "search_title": "Hanso GmbH", "segment": "accounting", "stage": "closed_lost", "value_eur": 35000, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "sec003"}}
response: {"blocker": "budget", "champion_present": true, "company": "Spectre Oy", "company_id": "spectre-oy", "created": "2025-07-04", "deal_id": "sec003", "last_touch_date": "2025-12-10", "probability": 70, "search_text": "Spectre Oy ecommerce closed_lost budget", "search_title": "Spectre Oy", "segment": "ecommerce", "stage": "closed_lost", "value_eur": 80000, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "sec004"}}
response: {"blocker": "none", "champion_present": false, "company": "Nakatomi O\u00dc", "company_id": "nakatomi-o", "created": "2025-07-04", "deal_id": "sec004", "last_touch_date": "2026-04-03", "probability": 20, "search_text": "Nakatomi O\u00dc erp closed_lost none", "search_title": "Nakatomi O\u00dc", "segment": "erp", "stage": "closed_lost", "value_eur": 15000, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "sec005"}}
response: {"blocker": "no_champion", "champion_present": false, "company": "Pied Oy", "company_id": "pied-oy", "created": "2024-08-26", "deal_id": "sec005", "last_touch_date": "2025-06-19", "probability": 70, "search_text": "Pied Oy accounting closed_lost no_champion", "search_title": "Pied Oy", "segment": "accounting", "stage": "closed_lost", "value_eur": 35000, "won": false}

## Sample rows: decisions

request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "sx041"}}
response: {"accepted": true, "agent_confidence": 0.66, "chosen": "sc037", "confidence_bucket": "medium", "context_ai_lifecycle": "operating", "context_segment": "analytics", "context_tier": "B", "context_weekday": "wed", "context_window": "0800", "decision_id": "sx041", "decision_type": "opener_choice", "human_action": "accepted", "ts": "2026-03-14T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "sx049"}}
response: {"accepted": false, "agent_confidence": 0.12, "chosen": "sc030", "confidence_bucket": "low", "context_ai_lifecycle": "announced", "context_segment": "accounting", "context_tier": "B", "context_weekday": "thu", "context_window": "1600", "decision_id": "sx049", "decision_type": "call_priority", "human_action": "overridden", "human_alternative": "reordered", "ts": "2026-03-14T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "sx014"}}
response: {"accepted": true, "agent_confidence": 0.83, "chosen": "sc054", "confidence_bucket": "high", "context_ai_lifecycle": "operating", "context_segment": "erp", "context_tier": "C", "context_weekday": "fri", "context_window": "0800", "decision_id": "sx014", "decision_type": "followup_timing", "human_action": "accepted", "outcome_after": "neutral", "ts": "2026-03-20T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "sx055"}}
response: {"accepted": true, "agent_confidence": 0.81, "chosen": "sc008", "confidence_bucket": "high", "context_ai_lifecycle": "operating", "context_segment": "accounting", "context_tier": "C", "context_weekday": "fri", "context_window": "0800", "decision_id": "sx055", "decision_type": "followup_timing", "human_action": "accepted", "ts": "2026-03-20T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "sx032"}}
response: {"accepted": false, "agent_confidence": 0.38, "chosen": "sc044", "confidence_bucket": "low", "context_ai_lifecycle": "shipped", "context_segment": "erp", "context_tier": "C", "context_weekday": "wed", "context_window": "0800", "decision_id": "sx032", "decision_type": "call_priority", "human_action": "overridden", "human_alternative": "reordered", "ts": "2026-03-23T08:10:00"}

## Sample rows: experiments

request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "sr046"}}
response: {"area": "retention", "baseline": 0.085, "created": "2026-01-18", "decided": "2026-02-16", "effort": "small", "experiment_id": "sr046", "hypothesis": "A pricing change lifts m1_retention from 0.085 to 0.122.", "learning": "m1_retention reached 0.151; shipped", "metric": "m1_retention", "result": 0.151, "started": "2026-01-18", "status": "validated", "target": 0.122, "type": "pricing", "validated": true}
request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "sr016"}}
response: {"area": "activation", "baseline": 0.393, "created": "2026-01-20", "effort": "small", "experiment_id": "sr016", "hypothesis": "A onboarding change lifts trial_start_rate from 0.393 to 0.548.", "learning": "killed before a verdict", "metric": "trial_start_rate", "started": "2026-01-20", "status": "abandoned", "target": 0.548, "type": "onboarding"}
request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "sr038"}}
response: {"area": "retention", "baseline": 0.28, "created": "2026-01-20", "decided": "2026-01-28", "effort": "medium", "experiment_id": "sr038", "hypothesis": "A onboarding change lifts m1_retention from 0.28 to 0.439.", "learning": "no lift over baseline; reverted", "metric": "m1_retention", "result": 0.258, "started": "2026-01-20", "status": "invalidated", "target": 0.439, "type": "onboarding", "validated": false}
request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "sr067"}}
response: {"area": "acquisition", "baseline": 0.268, "created": "2026-01-21", "effort": "small", "experiment_id": "sr067", "hypothesis": "A outreach change lifts signup_rate from 0.268 to 0.383.", "learning": "killed before a verdict", "metric": "signup_rate", "started": "2026-01-21", "status": "abandoned", "target": 0.383, "type": "outreach"}
request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "sr049"}}
response: {"area": "retention", "baseline": 0.34, "created": "2026-01-23", "decided": "2026-02-14", "effort": "small", "experiment_id": "sr049", "hypothesis": "A feature change lifts m1_retention from 0.34 to 0.564.", "learning": "m1_retention reached 0.662; shipped", "metric": "m1_retention", "result": 0.662, "started": "2026-01-23", "status": "validated", "target": 0.564, "type": "feature", "validated": true}

## Sample rows: events

request:  {"from": "events", "limit": 1, "where": {"event_id": "sv012"}}
response: {"cost_eur": 300, "created": "2026-04-26", "event_id": "sv012", "location": "Stockholm", "name": "SaaStr Europe 2026", "starts": "2026-04-17", "status": "candidate", "type": "meetup"}
request:  {"from": "events", "limit": 1, "where": {"event_id": "sv008"}}
response: {"cost_eur": 0, "created": "2026-03-17", "decided": "2026-04-17", "event_id": "sv008", "location": "Stockholm", "name": "AI Summit 2026", "notes": "post-event notes", "outcome": "neutral", "starts": "2026-05-07", "status": "attended", "type": "meetup"}
request:  {"from": "events", "limit": 1, "where": {"event_id": "sv002"}}
response: {"cost_eur": 600, "created": "2026-05-22", "decided": "2026-05-08", "event_id": "sv002", "location": "Helsinki", "name": "DevMeetup 2026", "notes": "low fit for the cost", "starts": "2026-05-20", "status": "no_go", "type": "conference"}
request:  {"from": "events", "limit": 1, "where": {"event_id": "sv013"}}
response: {"cost_eur": 0, "created": "2026-05-12", "decided": "2026-05-21", "event_id": "sv013", "location": "online", "name": "AI Summit 2026", "notes": "low fit for the cost", "starts": "2026-05-26", "status": "no_go", "type": "conference"}
request:  {"from": "events", "limit": 1, "where": {"event_id": "sv011"}}
response: {"cost_eur": 0, "created": "2026-03-24", "decided": "2026-05-22", "event_id": "sv011", "location": "Stockholm", "name": "Founders Brunch 2026", "notes": "worth a talk / booth", "starts": "2026-05-27", "status": "go", "type": "talk"}

## Sample rows: routines

request:  {"from": "routines", "limit": 1, "where": {"routine_id": "so01"}}
response: {"active": true, "area": "sales", "cadence": "weekly", "created": "2026-05-13", "notes": "next outbound batch", "prep": "prospects", "routine_id": "so01", "title": "Monday outreach prep", "weekday": "mon"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "so02"}}
response: {"active": true, "area": "operations", "cadence": "weekly", "created": "2026-05-13", "prep": "brief", "routine_id": "so02", "title": "Prepare the week", "weekday": "sun"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "so03"}}
response: {"active": true, "area": "operations", "cadence": "weekly", "created": "2026-05-13", "prep": "brief", "routine_id": "so03", "title": "Friday board review", "weekday": "fri"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "so04"}}
response: {"active": true, "area": "marketing", "cadence": "weekly", "created": "2026-05-13", "notes": "draft + schedule posts", "prep": "none", "routine_id": "so04", "title": "Weekly content batch", "weekday": "tue"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "so05"}}
response: {"active": true, "area": "sales", "cadence": "weekly", "created": "2026-05-13", "notes": "update stages, clear stale", "prep": "none", "routine_id": "so05", "title": "Pipeline hygiene", "weekday": "wed"}
