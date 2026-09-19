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
response: {"ai_lifecycle": "shipped", "company": "Aperture O\u00dc", "company_id": "aperture-o", "contact_id": "yc001", "country": "Estonia", "created": "2025-12-09", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": false, "name": "Niaj Cross", "notes_tags": "rfp-soon", "phone_present": true, "role": "Founder", "search_text": "Niaj Cross Aperture O\u00dc Founder accounting rfp-soon", "search_title": "Niaj Cross", "segment": "accounting", "source": "cold", "tier": "C"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "yc002"}}
response: {"ai_lifecycle": "none", "company": "Tyrell Oy", "company_id": "tyrell-oy", "contact_id": "yc002", "country": "Finland", "created": "2025-08-16", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": false, "name": "Mona Fields", "notes_tags": "rfp-soon tech-savvy", "phone_present": true, "role": "CEO", "search_text": "Mona Fields Tyrell Oy CEO erp rfp-soon tech-savvy", "search_title": "Mona Fields", "segment": "erp", "source": "cold", "tier": "C"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "yc003"}}
response: {"ai_lifecycle": "announced", "company": "Hanso Oy", "company_id": "hanso-oy", "contact_id": "yc003", "country": "Finland", "created": "2025-08-21", "email_present": true, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": false, "name": "Rupert Brooks", "notes_tags": "", "phone_present": true, "role": "Controller", "search_text": "Rupert Brooks Hanso Oy Controller accounting", "search_title": "Rupert Brooks", "segment": "accounting", "source": "cold", "tier": "C"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "yc004"}}
response: {"ai_lifecycle": "shipped", "company": "Sirius Oy", "company_id": "sirius-oy", "contact_id": "yc004", "country": "Finland", "created": "2025-12-03", "email_present": true, "ever_conversation": true, "ever_meeting": false, "ever_reached": true, "ever_touched": true, "name": "Quinn Snow", "notes_tags": "q3-budget slow-cycle", "phone_present": true, "role": "Controller", "search_text": "Quinn Snow Sirius Oy Controller other q3-budget slow-cycle", "search_title": "Quinn Snow", "segment": "other", "source": "warm", "tier": "A"}
request:  {"from": "contacts", "limit": 1, "where": {"contact_id": "yc005"}}
response: {"ai_lifecycle": "shipped", "company": "Initrode Oy", "company_id": "initrode-oy", "contact_id": "yc005", "country": "Finland", "created": "2025-05-28", "email_present": false, "ever_conversation": false, "ever_meeting": false, "ever_reached": false, "ever_touched": false, "name": "Hank Knight", "notes_tags": "q3-budget rfp-soon slow-cycle", "phone_present": true, "role": "CFO", "search_text": "Hank Knight Initrode Oy CFO accounting q3-budget rfp-soon slow-cycle", "search_title": "Hank Knight", "segment": "accounting", "source": "referral", "tier": "C"}

## Sample rows: touches

request:  {"from": "touches", "limit": 1, "where": {"touch_id": "yt009"}}
response: {"booked": false, "channel": "email", "contact_id": "yc008", "days_since_prev_touch": "first", "good_outcome": false, "next_action": "send one-pager", "next_action_due": "2026-04-13", "notes": "replied, lukewarm but open", "outcome": "reply", "reached": true, "touch_id": "yt009", "ts": "2026-04-09T18:45:00", "weekday": "thu", "window": "other"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "yt002"}}
response: {"booked": false, "channel": "linkedin", "contact_id": "yc009", "days_since_prev_touch": "first", "good_outcome": false, "outcome": "no_reply", "reached": false, "touch_id": "yt002", "ts": "2026-04-10T12:33:00", "weekday": "fri", "window": "1215"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "yt005"}}
response: {"booked": false, "channel": "call", "contact_id": "yc009", "days_since_prev_touch": "3-7", "good_outcome": false, "notes": "no budget this year", "outcome": "declined", "reached": true, "touch_id": "yt005", "ts": "2026-04-15T08:42:00", "weekday": "wed", "window": "0800"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "yt011"}}
response: {"booked": false, "channel": "linkedin", "contact_id": "yc004", "days_since_prev_touch": "first", "good_outcome": false, "next_action": "send one-pager", "next_action_due": "2026-04-24", "notes": "replied, lukewarm but open", "outcome": "reply", "reached": true, "touch_id": "yt011", "ts": "2026-04-23T09:28:00", "weekday": "thu", "window": "0800"}
request:  {"from": "touches", "limit": 1, "where": {"touch_id": "yt004"}}
response: {"booked": false, "channel": "email", "contact_id": "yc007", "days_since_prev_touch": "first", "good_outcome": false, "next_action": "send one-pager", "next_action_due": "2026-05-13", "notes": "replied, lukewarm but open", "outcome": "reply", "reached": true, "touch_id": "yt004", "ts": "2026-05-11T12:18:00", "weekday": "mon", "window": "1215"}

## Sample rows: sessions

request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ys0014"}}
response: {"converted_paid": true, "country": "Finland", "device": "desktop", "landing_page": "/pricing", "session_id": "ys0014", "signed_up": true, "source": "referral", "started_trial": true, "ts": "2026-02-16"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ys0011"}}
response: {"campaign": "retargeting", "converted_paid": false, "country": "Finland", "device": "tablet", "landing_page": "/pricing", "session_id": "ys0011", "signed_up": false, "source": "social", "started_trial": false, "ts": "2026-02-23"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ys0030"}}
response: {"campaign": "spring_launch", "converted_paid": false, "country": "Germany", "device": "desktop", "landing_page": "/demo", "session_id": "ys0030", "signed_up": false, "source": "social", "started_trial": false, "ts": "2026-02-23"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ys0018"}}
response: {"converted_paid": false, "country": "Finland", "device": "mobile", "landing_page": "/blog", "session_id": "ys0018", "signed_up": false, "source": "direct", "started_trial": false, "ts": "2026-03-06"}
request:  {"from": "sessions", "limit": 1, "where": {"session_id": "ys0004"}}
response: {"converted_paid": false, "country": "Germany", "device": "mobile", "landing_page": "/blog", "session_id": "ys0004", "signed_up": false, "source": "organic", "started_trial": false, "ts": "2026-03-17"}

## Sample rows: materials

request:  {"from": "materials", "limit": 1, "where": {"material_id": "ym001"}}
response: {"ai_made": "ai-assisted", "created": "2026-03-23", "lane": "cold", "length_chars": 180, "material_id": "ym001", "title": "positioning benchmark", "topic": "positioning", "type": "whitepaper"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "ym002"}}
response: {"ai_made": "manual", "created": "2026-05-08", "lane": "warm", "length_chars": 120, "material_id": "ym002", "title": "oss tool deep dive", "topic": "oss_tool", "type": "note"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "ym003"}}
response: {"ai_made": "ai-assisted", "created": "2026-05-18", "lane": "warm", "length_chars": 320, "material_id": "ym003", "title": "positioning benchmark", "topic": "positioning", "type": "demo"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "ym004"}}
response: {"ai_made": "manual", "created": "2026-02-28", "lane": "cold", "length_chars": 180, "material_id": "ym004", "title": "customer proof guide", "topic": "customer_proof", "type": "video"}
request:  {"from": "materials", "limit": 1, "where": {"material_id": "ym005"}}
response: {"ai_made": "ai-assisted", "created": "2026-03-11", "lane": "warm", "length_chars": 680, "material_id": "ym005", "title": "core product notes", "topic": "core_product", "type": "blog"}

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
response: {"ai_made": "ai", "channel_id": "yk01", "format": "link", "lane": "warm", "length_bucket": "short", "length_chars": 180, "link_placement": "n_a", "material_id": "ym007", "outcome": "flop", "platform": "hackernews", "post_id": "yp0012", "posted_at": "2026-02-16", "reach_or_views": 17, "status": "posted", "tone": "narrate", "topic": "customer_proof", "trials": 0, "upvotes": 0, "weekday": "mon", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "yp0003"}}
response: {"ai_made": "ai-assisted", "channel_id": "yk02", "format": "text", "lane": "cold", "length_bucket": "short", "length_chars": 180, "link_placement": "n_a", "material_id": "ym001", "outcome": "flop", "platform": "reddit", "post_id": "yp0003", "posted_at": "2026-03-09", "reach_or_views": 193, "status": "posted", "tone": "announce", "topic": "positioning", "trials": 0, "upvotes": 2, "weekday": "mon", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "yp0002"}}
response: {"ai_made": "manual", "channel_id": "yk01", "format": "link", "lane": "warm", "length_bucket": "short", "length_chars": 120, "link_placement": "n_a", "material_id": "ym002", "outcome": "flop", "platform": "hackernews", "post_id": "yp0002", "posted_at": "2026-04-07", "reach_or_views": 31, "status": "posted", "tone": "explainer", "topic": "oss_tool", "trials": 0, "upvotes": 0, "weekday": "tue", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "yp0009"}}
response: {"ai_made": "manual", "channel_id": "yk03", "format": "text", "lane": "cold", "length_bucket": "short", "length_chars": 180, "link_placement": "n_a", "material_id": "ym004", "outcome": "modest", "platform": "reddit", "post_id": "yp0009", "posted_at": "2026-04-21", "reach_or_views": 553, "status": "posted", "tone": "explainer", "topic": "customer_proof", "trials": 0, "upvotes": 8, "weekday": "tue", "won": false}
request:  {"from": "posts", "limit": 1, "where": {"post_id": "yp0011"}}
response: {"ai_made": "manual", "channel_id": "yk05", "format": "link", "lane": "warm", "length_bucket": "short", "length_chars": 120, "link_placement": "n_a", "material_id": "ym002", "outcome": "win", "platform": "blog", "post_id": "yp0011", "posted_at": "2026-04-21", "reach_or_views": 347, "status": "posted", "tone": "narrate", "topic": "oss_tool", "trials": 0, "upvotes": 4, "weekday": "tue", "won": true}

## Sample rows: todos

request:  {"from": "todos", "limit": 1, "where": {"todo_id": "yd002"}}
response: {"action_type": "post", "area": "marketing", "due_date": "2026-06-15", "linked_type": "asset", "prep_status": "ready", "priority": 1, "slot": "13:00", "status": "draft", "title": "Propagate the positioning demo", "todo_id": "yd002", "window": "fri_1530"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "yd004"}}
response: {"action_type": "post", "area": "marketing", "due_date": "2026-06-19", "linked_type": "asset", "prep_status": "ready", "priority": 2, "slot": "14:30", "status": "prog", "title": "Ship the customer-proof post", "todo_id": "yd004", "window": "fri_eve"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "yd003"}}
response: {"action_type": "admin", "area": "operations", "linked_type": "instance", "prep_status": "n_a", "priority": 2, "status": "monitor", "title": "Genco Oy license renewal window", "todo_id": "yd003"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "yd006"}}
response: {"action_type": "admin", "area": "operations", "linked_type": "instance", "prep_status": "n_a", "priority": 2, "status": "on_track", "title": "Pierce Oy usage anomaly review", "todo_id": "yd006"}
request:  {"from": "todos", "limit": 1, "where": {"todo_id": "yd005"}}
response: {"action_type": "research", "area": "rnd", "linked_type": "workstream", "prep_status": "in_progress", "priority": 2, "status": "prog", "title": "Rep2 stabilization", "todo_id": "yd005"}

## Sample rows: deals

request:  {"from": "deals", "limit": 1, "where": {"deal_id": "yec001"}}
response: {"blocker": "demo_readiness", "champion_present": false, "company": "Genco Oy", "company_id": "genco-oy", "created": "2025-03-07", "deal_id": "yec001", "last_touch_date": "2025-10-16", "probability": 20, "search_text": "Genco Oy accounting closed_lost demo_readiness", "search_title": "Genco Oy", "segment": "accounting", "stage": "closed_lost", "value_eur": 35000, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "yec002"}}
response: {"blocker": "budget", "champion_present": true, "company": "Pierce Oy", "company_id": "pierce-oy", "created": "2025-12-07", "deal_id": "yec002", "last_touch_date": "2026-01-19", "probability": 40, "search_text": "Pierce Oy ecommerce closed_lost budget", "search_title": "Pierce Oy", "segment": "ecommerce", "stage": "closed_lost", "value_eur": 22500, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "yec003"}}
response: {"blocker": "no_champion", "champion_present": false, "company": "Sirius Oy", "company_id": "sirius-oy", "created": "2025-12-13", "deal_id": "yec003", "last_touch_date": "2026-03-01", "probability": 70, "search_text": "Sirius Oy consultancy closed_lost no_champion", "search_title": "Sirius Oy", "segment": "consultancy", "stage": "closed_lost", "value_eur": 80000, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "yec004"}}
response: {"blocker": "timing_mismatch", "champion_present": true, "company": "Sabre BV", "company_id": "sabre-bv", "created": "2025-11-07", "deal_id": "yec004", "last_touch_date": "2026-01-29", "probability": 50, "search_text": "Sabre BV consultancy closed_lost timing_mismatch", "search_title": "Sabre BV", "segment": "consultancy", "stage": "closed_lost", "value_eur": 22500, "won": false}
request:  {"from": "deals", "limit": 1, "where": {"deal_id": "yec005"}}
response: {"blocker": "none", "champion_present": true, "company": "Wayne GmbH", "company_id": "wayne-gmbh", "created": "2025-02-28", "deal_id": "yec005", "last_touch_date": "2025-09-22", "probability": 70, "search_text": "Wayne GmbH other closed_lost none", "search_title": "Wayne GmbH", "segment": "other", "stage": "closed_lost", "value_eur": 45000, "won": false}

## Sample rows: decisions

request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "yx006"}}
response: {"accepted": true, "agent_confidence": 0.36, "chosen": "yc001", "confidence_bucket": "low", "context_ai_lifecycle": "shipped", "context_segment": "accounting", "context_tier": "C", "context_weekday": "tue", "context_window": "0800", "decision_id": "yx006", "decision_type": "opener_choice", "human_action": "accepted", "ts": "2026-03-21T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "yx003"}}
response: {"accepted": false, "agent_confidence": 0.81, "chosen": "yc001", "confidence_bucket": "high", "context_ai_lifecycle": "shipped", "context_segment": "accounting", "context_tier": "C", "context_weekday": "fri", "context_window": "0800", "decision_id": "yx003", "decision_type": "opener_choice", "human_action": "ignored", "ts": "2026-03-22T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "yx002"}}
response: {"accepted": true, "agent_confidence": 0.78, "chosen": "yc008", "confidence_bucket": "high", "context_ai_lifecycle": "announced", "context_segment": "erp", "context_tier": "A", "context_weekday": "thu", "context_window": "0800", "decision_id": "yx002", "decision_type": "followup_timing", "human_action": "accepted", "outcome_after": "good", "ts": "2026-03-24T08:10:00"}
request:  {"from": "decisions", "limit": 1, "where": {"decision_id": "yx008"}}
response: {"accepted": true, "agent_confidence": 0.28, "chosen": "yc003", "confidence_bucket": "low", "context_ai_lifecycle": "announced", "context_segment": "accounting", "context_tier": "C", "context_weekday": "fri", "context_window": "1600", "decision_id": "yx008", "decision_type": "opener_choice", "human_action": "accepted", "ts": "2026-04-12T08:10:00"}
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
response: {"active": true, "area": "sales", "cadence": "weekly", "created": "2026-05-13", "notes": "next outbound batch", "prep": "prospects", "routine_id": "yo01", "title": "Fill La Growth Machine", "weekday": "mon"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "yo02"}}
response: {"active": true, "area": "operations", "cadence": "weekly", "created": "2026-05-13", "prep": "brief", "routine_id": "yo02", "title": "Prepare the week", "weekday": "sun"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "yo03"}}
response: {"active": true, "area": "operations", "cadence": "weekly", "created": "2026-05-13", "prep": "brief", "routine_id": "yo03", "title": "Friday board review", "weekday": "fri"}
request:  {"from": "routines", "limit": 1, "where": {"routine_id": "yo04"}}
response: {"active": true, "area": "marketing", "cadence": "weekly", "created": "2026-05-13", "notes": "draft + schedule posts", "prep": "none", "routine_id": "yo04", "title": "Weekly content batch", "weekday": "tue"}
