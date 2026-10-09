# Loader gate: data/seed_tiny


## Schema


## Load

contacts:    rows in file = rows in Aito = 10
touches:     rows in file = rows in Aito = 15
sessions:    rows in file = rows in Aito = 30
materials:   rows in file = rows in Aito = 8
channels:    rows in file = rows in Aito = 5
posts:       rows in file = rows in Aito = 12
todos:       rows in file = rows in Aito = 16
deals:       rows in file = rows in Aito = 14
decisions:   rows in file = rows in Aito = 8
experiments: rows in file = rows in Aito = 6
events:      rows in file = rows in Aito = 4
routines:    rows in file = rows in Aito = 4

## Sample rows: contacts

request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "yc001"}}
response: {"ai_lifecycle": "none", "company": "Rekall Oy", "company_id": "rekall-oy", "contact_id": "yc001", "country": "Finland", "created": "2025-09-18", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": false, "name": "Zara Brooks", "notes_tags": "founder-led tech-savvy", "phone_present": true, "role": "Founder", "search_text": "Zara Brooks Rekall Oy Founder consultancy founder-led tech-savvy", "search_title": "Zara Brooks", "segment": "consultancy", "source": "referral", "tier": "C"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "yc002"}}
response: {"ai_lifecycle": "none", "company": "Genco Oy", "company_id": "genco-oy", "contact_id": "yc002", "country": "Finland", "created": "2025-06-08", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": false, "name": "Eve Pike", "notes_tags": "intro-available newsletter", "phone_present": true, "role": "CFO", "search_text": "Eve Pike Genco Oy CFO analytics intro-available newsletter", "search_title": "Eve Pike", "segment": "analytics", "source": "referral", "tier": "C"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "yc003"}}
response: {"ai_lifecycle": "shipped", "company": "Vertex O\u00dc", "company_id": "vertex-o", "contact_id": "yc003", "country": "Estonia", "created": "2025-08-24", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": true, "ever_touched": true, "name": "Carol Vale", "notes_tags": "q3-budget slow-cycle", "phone_present": true, "role": "CEO", "search_text": "Carol Vale Vertex O\u00dc CEO other q3-budget slow-cycle", "search_title": "Carol Vale", "segment": "other", "source": "warm", "tier": "A"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "yc004"}}
response: {"ai_lifecycle": "shipped", "company": "Vertex O\u00dc", "company_id": "vertex-o", "contact_id": "yc004", "country": "Estonia", "created": "2026-05-05", "email_present": true, "ever_conversation": true, "ever_meeting": true, "ever_reached": true, "ever_touched": true, "name": "Niaj Vale", "notes_tags": "q3-budget rfp-soon slow-cycle", "phone_present": true, "role": "Head of Product", "search_text": "Niaj Vale Vertex O\u00dc Head of Product other q3-budget rfp-soon slow-cycle", "search_title": "Niaj Vale", "segment": "other", "source": "cold", "tier": "A"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "yc005"}}
response: {"ai_lifecycle": "announced", "company": "Rekall Oy", "company_id": "rekall-oy", "contact_id": "yc005", "country": "Finland", "created": "2025-06-25", "email_present": true, "ever_conversation": true, "ever_meeting": true, "ever_reached": true, "ever_touched": true, "name": "Heidi Pike", "notes_tags": "", "phone_present": true, "role": "Finance Manager", "search_text": "Heidi Pike Rekall Oy Finance Manager consultancy", "search_title": "Heidi Pike", "segment": "consultancy", "source": "trigger", "tier": "A"}

## Sample rows: touches

request:  {"from": "touches", "limit": 1, "where": {"touch_id": "yt002"}}
response: {"booked": true, "channel": "call", "contact_id": "yc004", "days_since_prev_touch": "first", "good_outcome": true, "next_action": "prepare demo", "next_action_due": "2026-04-11", "notes": "agreed to a 30min walkthrough", "outcome": "meeting_booked", "reached": true, "touch_id": "yt002", "ts": "2026-04-07T08:32:00", "weekday": "tue", "window": "0800"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "yt011"}}
response: {"booked": false, "channel": "linkedin", "contact_id": "yc009", "days_since_prev_touch": "first", "good_outcome": false, "outcome": "no_reply", "reached": false, "touch_id": "yt011", "ts": "2026-04-23T09:28:00", "weekday": "thu", "window": "0800"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "yt001"}}
response: {"booked": false, "channel": "call", "contact_id": "yc006", "days_since_prev_touch": "first", "good_outcome": false, "outcome": "no_answer", "reached": false, "touch_id": "yt001", "ts": "2026-04-23T17:01:00", "weekday": "thu", "window": "1600"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "yt005"}}
response: {"booked": true, "channel": "call", "contact_id": "yc005", "days_since_prev_touch": "first", "good_outcome": true, "notes": "demo booked", "outcome": "meeting_booked", "reached": true, "touch_id": "yt005", "ts": "2026-05-26T12:20:00", "weekday": "tue", "window": "1215"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "yt008"}}
response: {"booked": false, "channel": "email", "contact_id": "yc003", "days_since_prev_touch": "first", "good_outcome": false, "next_action": "send one-pager", "next_action_due": "2026-05-27", "notes": "asked for a one-pager", "outcome": "reply", "reached": true, "touch_id": "yt008", "ts": "2026-05-26T16:43:00", "weekday": "tue", "window": "1600"}

## Sample rows: sessions

request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ys0015"}}
response: {"converted_paid": true, "country": "Finland", "device": "desktop", "landing_page": "/pricing", "session_id": "ys0015", "signed_up": true, "source": "referral", "started_trial": true, "ts": "2026-02-16"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ys0001"}}
response: {"converted_paid": false, "country": "Sweden", "device": "mobile", "landing_page": "/blog", "session_id": "ys0001", "signed_up": false, "source": "direct", "started_trial": false, "ts": "2026-02-17"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ys0012"}}
response: {"campaign": "retargeting", "converted_paid": false, "country": "Finland", "device": "tablet", "landing_page": "/pricing", "session_id": "ys0012", "signed_up": false, "source": "social", "started_trial": false, "ts": "2026-02-23"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ys0002"}}
response: {"converted_paid": false, "country": "Finland", "device": "mobile", "landing_page": "/pricing", "session_id": "ys0002", "signed_up": false, "source": "referral", "started_trial": false, "ts": "2026-03-01"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ys0019"}}
response: {"converted_paid": false, "country": "Finland", "device": "mobile", "landing_page": "/blog", "session_id": "ys0019", "signed_up": false, "source": "direct", "started_trial": false, "ts": "2026-03-06"}

## Sample rows: materials

request:  {"from": "materials", "limit": 1, "where": {"material_id": "ym001"}}
response: {"ai_made": "manual", "created": "2025-12-04", "lane": "warm", "length_chars": 180, "material_id": "ym001", "title": "oss tool guide", "topic": "oss_tool", "type": "whitepaper"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "ym002"}}
response: {"ai_made": "ai-assisted", "created": "2026-04-17", "lane": "warm", "length_chars": 180, "material_id": "ym002", "title": "core product deep dive", "topic": "core_product", "type": "note"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "ym003"}}
response: {"ai_made": "manual", "created": "2026-05-20", "lane": "warm", "length_chars": 540, "material_id": "ym003", "title": "positioning deep dive", "topic": "positioning", "type": "blog"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "ym004"}}
response: {"ai_made": "ai", "created": "2025-12-13", "lane": "warm", "length_chars": 420, "material_id": "ym004", "title": "product notes", "topic": "product", "type": "video"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "ym005"}}
response: {"ai_made": "manual", "created": "2026-04-21", "lane": "cold", "length_chars": 120, "material_id": "ym005", "title": "positioning story", "topic": "positioning", "type": "whitepaper"}

## Sample rows: channels

request:  {"from": "channels", "limit": 1, "where": {"channel_id": "yk01"}}
response: {"channel_id": "yk01", "created": "2025-05-08", "name": "Hacker News", "platform": "hackernews"}
request:  {"from": "channels", "limit": 1, "where": {"channel_id": "yk02"}}
response: {"channel_id": "yk02", "created": "2025-05-08", "name": "r/programming", "platform": "reddit"}
request:  {"from": "channels", "limit": 1, "where": {"channel_id": "yk03"}}
response: {"channel_id": "yk03", "created": "2025-05-08", "name": "r/Python", "platform": "reddit"}
request:  {"from": "channels", "limit": 1, "where": {"channel_id": "yk04"}}
response: {"channel_id": "yk04", "created": "2025-05-08", "name": "LinkedIn", "platform": "linkedin"}
request:  {"from": "channels", "limit": 1, "where": {"channel_id": "yk05"}}
response: {"channel_id": "yk05", "created": "2025-05-08", "name": "Company blog", "platform": "blog"}

## Sample rows: posts

request:  {"from": "posts", "limit": 1, "where": {"post_id": "yp0012"}}
response: {"ai_made": "manual", "channel_id": "yk01", "format": "link", "lane": "warm", "length_bucket": "short", "length_chars": 120, "link_placement": "n_a", "material_id": "ym007", "outcome": "modest", "platform": "hackernews", "post_id": "yp0012", "posted_at": "2026-02-16", "reach_or_views": 57, "status": "posted", "tone": "narrate", "topic": "positioning", "trials": 0, "upvotes": 0, "weekday": "mon", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "yp0010"}}
response: {"ai_made": "manual", "channel_id": "yk05", "format": "link", "lane": "warm", "length_bucket": "short", "length_chars": 120, "link_placement": "n_a", "material_id": "ym007", "outcome": "modest", "platform": "blog", "post_id": "yp0010", "posted_at": "2026-03-06", "reach_or_views": 205, "status": "posted", "tone": "builder", "topic": "positioning", "trials": 0, "upvotes": 3, "weekday": "fri", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "yp0009"}}
response: {"ai_made": "ai", "channel_id": "yk03", "format": "text", "lane": "warm", "length_bucket": "medium", "length_chars": 420, "link_placement": "n_a", "material_id": "ym004", "outcome": "flop", "platform": "reddit", "post_id": "yp0009", "posted_at": "2026-04-21", "reach_or_views": 174, "status": "posted", "tone": "explainer", "topic": "product", "trials": 0, "upvotes": 2, "weekday": "tue", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "yp0011"}}
response: {"ai_made": "ai-assisted", "channel_id": "yk05", "format": "link", "lane": "warm", "length_bucket": "short", "length_chars": 180, "link_placement": "n_a", "material_id": "ym002", "outcome": "win", "platform": "blog", "post_id": "yp0011", "posted_at": "2026-04-21", "reach_or_views": 330, "status": "posted", "tone": "narrate", "topic": "core_product", "trials": 0, "upvotes": 4, "weekday": "tue", "won": true}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "yp0003"}}
response: {"ai_made": "manual", "channel_id": "yk01", "format": "show-hn", "lane": "warm", "length_bucket": "short", "length_chars": 180, "link_placement": "n_a", "material_id": "ym001", "outcome": "flop", "platform": "hackernews", "post_id": "yp0003", "posted_at": "2026-04-26", "reach_or_views": 20, "status": "posted", "tone": "announce", "topic": "oss_tool", "trials": 0, "upvotes": 0, "weekday": "sun", "won": false}

## Sample rows: todos

request:  {"from": "todos", "limit": 1, "where": {"todo_id": "yd003"}}
response: {"action_type": "research", "area": "experiments", "linked_type": "workstream", "prep_status": "prep_needed", "priority": 2, "rev": "rv-0", "revs": "rv-0", "status": "blocked", "title": "Set up the customer-proof experiment", "todo_id": "yd003"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "yd001"}}
response: {"action_type": "post", "area": "marketing", "due_date": "2026-06-12", "linked_type": "asset", "prep_status": "ready", "priority": 3, "rev": "rv-0", "revs": "rv-0", "slot": "14:30", "status": "prog", "title": "Ship the customer-proof post", "todo_id": "yd001", "window": "tue_0800"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "yd005"}}
response: {"action_type": "post", "area": "marketing", "due_date": "2026-06-17", "linked_type": "asset", "prep_status": "ready", "priority": 3, "rev": "rv-0", "revs": "rv-0", "slot": "09:00", "status": "draft", "title": "Propagate the customer-proof demo", "todo_id": "yd005", "window": "mon_0800"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "yd006"}}
response: {"action_type": "admin", "area": "operations", "due_date": "2026-06-15", "linked_type": "instance", "prep_status": "n_a", "priority": 3, "rev": "rv-0", "revs": "rv-0", "slot": "16:00", "status": "on_track", "title": "Nimbus GmbH license renewal window", "todo_id": "yd006"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "yd004"}}
response: {"action_type": "research", "area": "rnd", "linked_type": "workstream", "prep_status": "prep_needed", "priority": 1, "rev": "rv-0", "revs": "rv-0", "status": "blocked", "title": "Predictive-DB benchmark", "todo_id": "yd004"}

## Sample rows: deals

request:  {"from": "deals", "limit": 1, "where": {"deal_id": "yec001"}}
response: {"blocker": "demo_readiness", "champion_present": false, "company": "Genco Oy", "company_id": "genco-oy", "created": "2025-03-07", "deal_id": "yec001", "last_touch_date": "2025-10-16", "probability": 20, "search_text": "Genco Oy analytics closed_lost demo_readiness", "search_title": "Genco Oy", "segment": "analytics", "stage": "closed_lost", "value_eur": 35000, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "yec002"}}
response: {"blocker": "budget", "champion_present": true, "company": "Pied O\u00dc", "company_id": "pied-o", "created": "2025-12-07", "deal_id": "yec002", "last_touch_date": "2026-01-19", "probability": 40, "search_text": "Pied O\u00dc consultancy closed_lost budget", "search_title": "Pied O\u00dc", "segment": "consultancy", "stage": "closed_lost", "value_eur": 22500, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "yec003"}}
response: {"blocker": "no_champion", "champion_present": false, "company": "Vertex O\u00dc", "company_id": "vertex-o", "created": "2025-12-13", "deal_id": "yec003", "last_touch_date": "2026-03-01", "probability": 70, "search_text": "Vertex O\u00dc other closed_lost no_champion", "search_title": "Vertex O\u00dc", "segment": "other", "stage": "closed_lost", "value_eur": 60000, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "yec004"}}
response: {"blocker": "timing_mismatch", "champion_present": true, "company": "Vertex O\u00dc", "company_id": "vertex-o", "created": "2025-11-07", "deal_id": "yec004", "last_touch_date": "2026-01-29", "probability": 50, "search_text": "Vertex O\u00dc other closed_lost timing_mismatch", "search_title": "Vertex O\u00dc", "segment": "other", "stage": "closed_lost", "value_eur": 22500, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "yec005"}}
response: {"blocker": "none", "champion_present": true, "company": "Nimbus GmbH", "company_id": "nimbus-gmbh", "created": "2025-01-31", "deal_id": "yec005", "last_touch_date": "2025-09-22", "probability": 70, "search_text": "Nimbus GmbH erp closed_lost none", "search_title": "Nimbus GmbH", "segment": "erp", "stage": "closed_lost", "value_eur": 80000, "won": false}

## Sample rows: decisions

request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "yx006"}}
response: {"accepted": true, "agent_confidence": 0.36, "chosen": "yc001", "confidence_bucket": "low", "context_ai_lifecycle": "none", "context_segment": "consultancy", "context_tier": "C", "context_weekday": "tue", "context_window": "0800", "decision_id": "yx006", "decision_type": "opener_choice", "human_action": "accepted", "ts": "2026-03-21T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "yx003"}}
response: {"accepted": false, "agent_confidence": 0.81, "chosen": "yc001", "confidence_bucket": "high", "context_ai_lifecycle": "none", "context_segment": "consultancy", "context_tier": "C", "context_weekday": "fri", "context_window": "0800", "decision_id": "yx003", "decision_type": "opener_choice", "human_action": "ignored", "ts": "2026-03-22T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "yx002"}}
response: {"accepted": true, "agent_confidence": 0.78, "chosen": "yc008", "confidence_bucket": "high", "context_ai_lifecycle": "announced", "context_segment": "consultancy", "context_tier": "C", "context_weekday": "thu", "context_window": "0800", "decision_id": "yx002", "decision_type": "followup_timing", "human_action": "accepted", "outcome_after": "good", "ts": "2026-03-24T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "yx008"}}
response: {"accepted": true, "agent_confidence": 0.28, "chosen": "yc003", "confidence_bucket": "low", "context_ai_lifecycle": "shipped", "context_segment": "other", "context_tier": "A", "context_weekday": "fri", "context_window": "1600", "decision_id": "yx008", "decision_type": "opener_choice", "human_action": "accepted", "ts": "2026-04-12T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "yx005"}}
response: {"accepted": true, "agent_confidence": 0.24, "chosen": "yc007", "confidence_bucket": "low", "context_ai_lifecycle": "shipped", "context_segment": "consultancy", "context_tier": "B", "context_weekday": "wed", "context_window": "1600", "decision_id": "yx005", "decision_type": "followup_timing", "human_action": "accepted", "outcome_after": "good", "ts": "2026-04-18T08:10:00"}

## Sample rows: experiments

request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "yr004"}}
response: {"area": "retention", "baseline": 0.19, "created": "2026-01-26", "effort": "large", "experiment_id": "yr004", "hypothesis": "A content change lifts m1_retention from 0.19 to 0.316.", "metric": "m1_retention", "started": "2026-01-26", "status": "running", "target": 0.316, "type": "content"}
request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "yr002"}}
response: {"area": "retention", "baseline": 0.318, "created": "2026-03-01", "decided": "2026-03-22", "effort": "medium", "experiment_id": "yr002", "hypothesis": "A onboarding change lifts m1_retention from 0.318 to 0.399.", "learning": "no lift over baseline; reverted", "metric": "m1_retention", "result": 0.281, "started": "2026-03-01", "status": "invalidated", "target": 0.399, "type": "onboarding", "validated": false}
request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "yr006"}}
response: {"area": "acquisition", "baseline": 0.345, "created": "2026-03-30", "effort": "large", "experiment_id": "yr006", "hypothesis": "A pricing change lifts signup_rate from 0.345 to 0.584.", "metric": "signup_rate", "started": "2026-03-30", "status": "running", "target": 0.584, "type": "pricing"}
request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "yr001"}}
response: {"area": "retention", "baseline": 0.185, "created": "2026-04-02", "decided": "2026-04-22", "effort": "large", "experiment_id": "yr001", "hypothesis": "A pricing change lifts m1_retention from 0.185 to 0.323.", "learning": "signal within noise; needs a bigger sample", "metric": "m1_retention", "result": 0.32, "started": "2026-04-02", "status": "inconclusive", "target": 0.323, "type": "pricing"}
request:  {"from": "experiments", "limit": 1, "where": {"experiment_id": "yr003"}}
response: {"area": "referral", "baseline": 0.061, "created": "2026-04-05", "decided": "2026-05-02", "effort": "medium", "experiment_id": "yr003", "hypothesis": "A onboarding change lifts referral_rate from 0.061 to 0.107.", "learning": "signal within noise; needs a bigger sample", "metric": "referral_rate", "result": 0.105, "started": "2026-04-05", "status": "inconclusive", "target": 0.107, "type": "onboarding"}

## Sample rows: events

request:  {"from": "events", "limit": 1, "where": {"event_id": "yv004"}}
response: {"cost_eur": 300, "created": "2026-03-23", "event_id": "yv004", "location": "Berlin", "name": "Indie Hackers 2026", "starts": "2026-08-17", "status": "candidate", "type": "conference"}
request:  {"from": "events", "limit": 1, "where": {"event_id": "yv002"}}
response: {"cost_eur": 0, "created": "2026-05-09", "decided": "2026-09-05", "event_id": "yv002", "location": "online", "name": "DevMeetup 2026", "notes": "post-event notes", "outcome": "neutral", "starts": "2026-09-10", "status": "attended", "type": "webinar"}
request:  {"from": "events", "limit": 1, "where": {"event_id": "yv001"}}
response: {"cost_eur": 0, "created": "2026-02-27", "decided": "2026-08-28", "event_id": "yv001", "location": "online", "name": "Postgres Conf 2026", "notes": "low fit for the cost", "starts": "2026-09-17", "status": "no_go", "type": "conference"}
request:  {"from": "events", "limit": 1, "where": {"event_id": "yv003"}}
response: {"cost_eur": 600, "created": "2026-03-27", "event_id": "yv003", "location": "Helsinki", "name": "ML Connect 2026", "starts": "2026-10-04", "status": "candidate", "type": "webinar"}

## Sample rows: routines

request:  {"from": "routines", "limit": 1, "where": {"routine_id": "yo01"}}
response: {"active": true, "area": "sales", "cadence": "weekly", "created": "2026-05-13", "notes": "next outbound batch", "prep": "prospects", "routine_id": "yo01", "title": "Monday outreach prep", "weekday": "mon"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "yo02"}}
response: {"active": true, "area": "operations", "cadence": "weekly", "created": "2026-05-13", "prep": "brief", "routine_id": "yo02", "title": "Prepare the week", "weekday": "sun"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "yo03"}}
response: {"active": true, "area": "operations", "cadence": "weekly", "created": "2026-05-13", "prep": "brief", "routine_id": "yo03", "title": "Friday board review", "weekday": "fri"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "yo04"}}
response: {"active": true, "area": "marketing", "cadence": "weekly", "created": "2026-05-13", "notes": "draft + schedule posts", "prep": "none", "routine_id": "yo04", "title": "Weekly content batch", "weekday": "tue"}
