"""Aito table definitions. The contract is docs/02-schema.md.

Two mappings worth noting:
- notes_tags is a whitespace-analyzed Text column: Aito treats each tag as
  a token, which is its idiomatic encoding of a tag array.
- decisions.context is an object in the docs; Aito columns are flat, so it
  is stored as context_* columns, one per documented context key.
"""

# companies — the customer/prospect ENTITY (.ai/tasks/15, the entity graph).
# Promotes `company` from a denormalised string (on contacts/deals/…) to a
# first-class node with an Aito `link`, so relational queries ("contacts at
# companies with a stalled deal") and inference (`_recommend` a company by
# P(win)) traverse the graph instead of a hand-joined string match. Built by the
# loader from the distinct company names across the CSVs; `company_id` is a name
# slug (the link target). Created before contacts/deals (its link dependents).
# The company node carries FACTS, not just a name. Everything below is
# harvested at load time from the rows that already link here (contacts and
# deals) — the same "derive it from the data" move as derive_contact_funnel.
# Without them the hub is unqueryable: "which accounts pay us?" has no column
# to ask about, and every such question has to be answered by hand-joining the
# spokes. With them, one `where` answers it, and a link hop answers it *about
# the spokes* ("contacts at paying customers") — see docs/31-knowledge-graph.md.
COMPANIES = {
    "type": "table",
    "columns": {
        "company_id": {"type": "String"},          # slug of the name — the link key
        "name": {"type": "String"},
        # harvested facts
        "industry": {"type": "String"},            # modal segment across its contacts/deals
        "relationship": {"type": "String"},        # COMPANY_RELATIONSHIPS, from deal outcomes
        "country": {"type": "String"},             # modal country across its contacts
        "mrr_eur": {"type": "Int"},                # won value / 12, 0 when nothing won
        "open_deals": {"type": "Int"},
        "contact_count": {"type": "Int"},
    },
}

# What the company is to us, derived from its deals: a won deal makes it a
# customer, an open one a prospect, only-lost deals `lost`, and no deals at all
# `none` (it is in the rolodex but has never been sold to).
COMPANY_RELATIONSHIPS = {"customer", "prospect", "lost", "none"}

CONTACTS = {
    "type": "table",
    "columns": {
        "contact_id": {"type": "String"},
        "name": {"type": "String"},
        "company": {"type": "String"},
        # first-class link to the company entity (derived: slug of `company`).
        "company_id": {"type": "String", "link": "companies.company_id"},
        "role": {"type": "String"},
        "phone_present": {"type": "Boolean"},
        "email_present": {"type": "Boolean"},
        "segment": {"type": "String"},
        "tier": {"type": "String"},
        "ai_lifecycle": {"type": "String"},
        "source": {"type": "String"},
        "country": {"type": "String"},
        "notes_tags": {"type": "Text", "analyzer": "whitespace"},
        "created": {"type": "String"},
        # derived at load, for the search view only: v2 unions merge text with
        # `$text`, which needs Text columns, and the identifying fields above
        # are categorical String (predict conditions on them — never retype
        # them). These carry the same words as analysable Text. See docs/23.
        # MUST be non-nullable Text: the search_items union view's `$text` source
        # rejects a nullable column ("must be a Text column, but is NullableType").
        # Consequence (docs/23): these can't be ADDED to a populated table in place
        # — a non-nullable column needs a fill value, a nullable one is refused by
        # the view, and Aito won't promote nullable→non-nullable. Adding them to an
        # instance that predates them requires a RELOAD of the table (export-all →
        # load-rolodex/load-deals), which recreates it with the columns populated.
        "search_title": {"type": "Text", "analyzer": "english"},
        "search_text": {"type": "Text", "analyzer": "english"},
        # derived from touches at load time, never in CSV: the contact's
        # furthest sales-funnel stage. Monotone: meeting => conversation =>
        # reached => touched. Feeds the sales funnel (docs/09-funnels.md).
        "ever_touched": {"type": "Boolean"},
        "ever_reached": {"type": "Boolean"},
        "ever_conversation": {"type": "Boolean"},
        "ever_meeting": {"type": "Boolean"},
    },
}

TOUCHES = {
    "type": "table",
    "columns": {
        "touch_id": {"type": "String"},
        "contact_id": {"type": "String", "link": "contacts.contact_id"},
        "ts": {"type": "String"},
        "weekday": {"type": "String"},
        "window": {"type": "String"},
        "channel": {"type": "String"},
        "outcome": {"type": "String"},
        # derived at load/log time, never present in CSV: recency state at the
        # moment of the touch, the days_since_last_touch feature of query 1
        "days_since_prev_touch": {"type": "String"},
        # derived KPI labels (deterministic relabelings of outcome) so the
        # 360 dashboard can _predict a clean $p + $why per KPI; see analytics.py
        "good_outcome": {"type": "Boolean"},
        "reached": {"type": "Boolean"},
        "booked": {"type": "Boolean"},
        "next_action": {"type": "Text", "analyzer": "english", "nullable": True},
        "next_action_due": {"type": "String", "nullable": True},
        "notes": {"type": "Text", "analyzer": "english", "nullable": True},
    },
}

DECISIONS = {
    "type": "table",
    "columns": {
        "decision_id": {"type": "String"},
        "ts": {"type": "String"},
        "decision_type": {"type": "String"},
        "context_window": {"type": "String", "nullable": True},
        "context_weekday": {"type": "String", "nullable": True},
        "context_segment": {"type": "String", "nullable": True},
        "context_tier": {"type": "String", "nullable": True},
        "context_ai_lifecycle": {"type": "String", "nullable": True},
        "chosen": {"type": "String"},
        "agent_confidence": {"type": "Decimal"},
        "human_action": {"type": "String"},
        "human_alternative": {"type": "String", "nullable": True},
        "outcome_after": {"type": "String", "nullable": True},
        # derived: the dogfood predictor's features/target — does the operator
        # accept the agent's recommendation, and is the agent's confidence
        # trustworthy? Nullable so create-schema can add them to an already-
        # populated table (existing rows read null until reloaded).
        "confidence_bucket": {"type": "String", "nullable": True},   # low/medium/high
        "accepted": {"type": "Boolean", "nullable": True},           # human_action == accepted
    },
}

# sessions — the website / acquisition funnel. One row per visitor session.
# Stage booleans are monotone: converted_paid => started_trial => signed_up.
# This is the inbound counterpart to the outbound touches table; `source` and
# `campaign` are the marketing dimensions. See docs/09-funnels.md.
SESSIONS = {
    "type": "table",
    "columns": {
        "session_id": {"type": "String"},
        "ts": {"type": "String"},
        "source": {"type": "String"},        # organic, paid_search, social, referral, direct
        "campaign": {"type": "String", "nullable": True},
        "landing_page": {"type": "String"},
        "country": {"type": "String"},
        "device": {"type": "String"},         # desktop, mobile, tablet
        "signed_up": {"type": "Boolean"},
        "started_trial": {"type": "Boolean"},
        "converted_paid": {"type": "Boolean"},
    },
}

# materials — the content catalog (a blog post, a demo, a whitepaper). The
# content exists independently of where it's posted; its attributes (topic,
# lane, ai_made, length) belong here. See docs/10-messaging-formula.md.
MATERIALS = {
    "type": "table",
    "columns": {
        "material_id": {"type": "String"},
        "type": {"type": "String"},          # blog, whitepaper, demo, video, talk, thread, note, other
        "title": {"type": "Text", "analyzer": "english"},
        "topic": {"type": "String"},
        "lane": {"type": "String"},           # warm, cold
        "ai_made": {"type": "String"},        # manual, ai-assisted, ai
        "length_chars": {"type": "Int"},
        "created": {"type": "String"},
    },
}

# channels — the destination catalog (Hacker News, r/programming, LinkedIn,
# the blog). A channel rolls up to a `platform`; the scorer predicts the win
# rate per platform (enough data), sharpening per channel as posts accrue.
CHANNELS = {
    "type": "table",
    "columns": {
        "channel_id": {"type": "String"},
        "name": {"type": "String"},           # "Hacker News", "r/programming", "LinkedIn"
        "platform": {"type": "String"},       # linkedin, hackernews, reddit, blog (PLATFORMS)
        "created": {"type": "String"},
    },
}

# posts — a material posted (or planned) to a channel: the go/no-go decision,
# the post-level details, and the KPIs. The scorer predicts `won` from the
# feature vector; the per-platform success metric is encoded by how `won` is
# defined (LinkedIn = reach, HN = views — never upvotes). The material's and
# channel's attributes (platform, ai_made, lane, topic, length) are
# denormalized onto the row at load so the prediction stays one query.
# docs/10-messaging-formula.md and .ai/input/operator-ground-truth.md §3.
POSTS = {
    "type": "table",
    "columns": {
        "post_id": {"type": "String"},
        "material_id": {"type": "String"},
        "channel_id": {"type": "String"},
        "status": {"type": "String"},            # planned, go, no_go, posted (the go/no-go lifecycle)
        "posted_at": {"type": "String", "nullable": True},   # set once posted
        "weekday": {"type": "String", "nullable": True},     # derived from posted_at
        "tone": {"type": "String"},              # narrate, announce, explainer, builder
        "format": {"type": "String"},            # text, link, demo-link, thread, show-hn
        "link_placement": {"type": "String"},    # comment, body, n_a
        "reach_or_views": {"type": "Int", "nullable": True},  # per-platform outcome (set once measured)
        "upvotes": {"type": "Int", "nullable": True},         # logged, NEVER the target
        "trials": {"type": "Int", "nullable": True},          # PLG attribution for cold drops
        "outcome": {"type": "String", "nullable": True},      # flop, modest, win (once measured)
        # denormalized from channel/material for a single-query predict:
        "platform": {"type": "String"},          # from the channel
        "ai_made": {"type": "String"},            # from the material
        "lane": {"type": "String"},               # from the material
        "topic": {"type": "String"},              # from the material
        "length_chars": {"type": "Int"},          # from the material
        "length_bucket": {"type": "String"},      # derived: short, medium, long
        "won": {"type": "Boolean", "nullable": True},  # derived: posted & outcome==win (scorer target)
    },
}

# todos — the unified action source (architecture spec rev 3 §2.9). One row
# per action. Both action lenses read from here: action-pipeline ranks by
# priority (Operations / R&D), action-calendar lays out by due_date (Sales /
# Distribution), and Now pulls the most urgent across all areas. `linked_id`
# ties a todo to a contact/asset so completing it can update that record.
# Titles are synthetic in seed (no PII). See docs/12-todos-and-now.md.
TODOS = {
    "type": "table",
    "columns": {
        "todo_id": {"type": "String"},
        "area": {"type": "String"},          # sales, distribution, operations, rnd, experiments
        # analyzed so Aito can _predict area/action_type from the title's words
        # (the auto-assign suggester, classify.py)
        "title": {"type": "Text", "analyzer": "english"},
        "detail": {"type": "Text", "analyzer": "english", "nullable": True},
        "action_type": {"type": "String", "nullable": True},  # call, email, meeting, ... (see ACTION_TYPES)
        "status": {"type": "String"},        # ready, draft, prog, blocked, done, monitor, on_track
        "priority": {"type": "Int"},         # 1 = highest
        "due_date": {"type": "String", "nullable": True},   # ISO date; empty for ranked areas
        "window": {"type": "String", "nullable": True},     # e.g. fri_1430; with due_date
        "slot": {"type": "String", "nullable": True},        # HH:MM clock time; shown in the calendar
        # operator's drag order within a pipeline list; null until dragged, then
        # the list sorts by it (priority stays the importance tag / predictor
        # feature). Set only via reorder_todos, never from CSV.
        "sort_order": {"type": "Int", "nullable": True},
        # the deal/asset/instance/workstream the action advances …
        "linked_id": {"type": "String", "nullable": True},
        "linked_type": {"type": "String", "nullable": True},  # deal, asset, instance, workstream
        # … and the person it concerns (a contact). company is derived from
        # either link for display, never stored (one source of truth).
        "stakeholder_id": {"type": "String", "nullable": True},
        "prep_status": {"type": "String"},   # prep_needed, ready, in_progress, blocked, n_a
        # outcome label for closed todos: did it slip past its intended
        # completion? null while open. The slip-risk predictor learns from
        # the closed rows; the open worklist (status != done) is what the
        # lenses show. See docs/12-todos-and-now.md.
        "slipped": {"type": "Boolean", "nullable": True},
        # --- work routing, for agent lanes (docs/12) ---
        # WHICH LANE the work belongs to: a repo slug, a surface, or `operator`.
        # An agent filters its queue on this. Free-form slug rather than an enum
        # — which lanes exist is deployment-specific, unlike `area`, which is
        # architectural.
        "role": {"type": "String", "nullable": True},
        # WHICH AGENT INSTANCE is meant to do it, when a role has more than one
        # (`core-a`, `core-b`). Assigned by the operator up front: two agents
        # sharing a role must be given disjoint work, because this instance has
        # no way to make a self-service claim safe — see docs/12 and
        # `_modify`-staleness in log.update_todo's docstring. null = the role's
        # shared queue, which only one agent per role may work.
        "owner": {"type": "String", "nullable": True},
    },
}

# deals — the sales pipeline (architecture spec §2.1). One row per
# opportunity. Open deals are the current pipeline; closed deals (won/lost)
# are the substrate the close-likelihood / risk predictor learns from. A
# todo can link to a deal (linked_type=deal), so resolving an action can
# advance its deal. Synthetic seed (no PII). See docs/13-deals.md.
DEALS = {
    "type": "table",
    "columns": {
        "deal_id": {"type": "String"},
        "company": {"type": "String"},
        # first-class link to the company entity (derived: slug of `company`).
        "company_id": {"type": "String", "link": "companies.company_id"},
        "segment": {"type": "String"},        # the offer segment (mirrors contacts.segment)
        "stage": {"type": "String"},          # lead..negotiation, closed_won/lost, parked
        "value_eur": {"type": "Int"},
        "probability": {"type": "Int"},       # 0-100, operator's own estimate
        "champion_present": {"type": "Boolean"},
        "blocker": {"type": "String"},        # none, consultant_lock, timing_mismatch, ...
        "last_touch_date": {"type": "String"},
        "created": {"type": "String"},
        # derived at load: terminal state of the deal, the predictor target.
        # true=closed_won, false=closed_lost, null=still open.
        "won": {"type": "Boolean", "nullable": True},
        # derived at load, for the search view only — see CONTACTS.search_text.
        # Non-nullable (the $text view rejects nullable); adding to a populated
        # instance needs a reload, not create-schema. See CONTACTS + docs/23.
        "search_title": {"type": "Text", "analyzer": "english"},
        "search_text": {"type": "Text", "analyzer": "english"},
    },
}

EXPERIMENTS = {
    "type": "table",
    "columns": {
        "experiment_id": {"type": "String"},
        "created": {"type": "String"},
        "area": {"type": "String"},        # AARRR: acquisition/activation/revenue/...
        "type": {"type": "String"},        # landing_page/pricing/onboarding/outreach/...
        "hypothesis": {"type": "Text", "analyzer": "english"},
        "metric": {"type": "String"},      # the one metric being moved
        "baseline": {"type": "Decimal"},   # its value now
        "target": {"type": "Decimal"},     # the value that would validate the bet
        "result": {"type": "Decimal", "nullable": True},   # observed once measured
        "effort": {"type": "String"},      # small/medium/large (the build cost)
        "status": {"type": "String"},      # running/validated/invalidated/...
        "learning": {"type": "Text", "analyzer": "english", "nullable": True},
        "started": {"type": "String"},
        "decided": {"type": "String", "nullable": True},
        # derived at load: the predictor target — did the bet pay off? true if
        # status==validated, false if invalidated, null while running/abandoned.
        "validated": {"type": "Boolean", "nullable": True},
    },
}

# events to attend (conferences, meetups, webinars), each with a go/no-go
# decision: a candidate becomes go or no_go, and a go you actually went to
# becomes attended (with an outcome). Same lifecycle shape as posts.
EVENTS = {
    "type": "table",
    "columns": {
        "event_id": {"type": "String"},
        "name": {"type": "Text", "analyzer": "english"},
        "type": {"type": "String"},          # conference, meetup, webinar, talk, demo, sponsor, other
        "starts": {"type": "String"},         # ISO date the event happens
        "location": {"type": "String", "nullable": True},   # "online" or a city
        "cost_eur": {"type": "Int", "nullable": True},      # cost to attend (informs go/no-go)
        "status": {"type": "String"},         # candidate, go, no_go, attended
        "decided": {"type": "String", "nullable": True},    # when the go/no-go was made
        "outcome": {"type": "String", "nullable": True},    # worthwhile, neutral, waste (after attending)
        "notes": {"type": "Text", "analyzer": "english", "nullable": True},
        "created": {"type": "String"},
    },
}

# routines — recurring agentic tasks (prepare the week, Monday outreach prep,
# monthly bookkeeping). A routine has a cadence and a `prep` recipe; "preparing"
# it pulls Aito-grounded data and fills a Claude-Desktop prompt (the app
# prepares, Claude runs — rule 1). Due-ness is computed from cadence +
# last_done; no scheduler in the repo. See docs/18-routines.md.
ROUTINES = {
    "type": "table",
    "columns": {
        "routine_id": {"type": "String"},
        "title": {"type": "Text", "analyzer": "english"},
        "area": {"type": "String"},           # sales/marketing/operations/rnd/experiments
        "cadence": {"type": "String"},        # daily, weekly, monthly
        "weekday": {"type": "String", "nullable": True},     # mon..sun, for weekly
        "day_of_month": {"type": "Int", "nullable": True},   # 1..28, for monthly
        "prep": {"type": "String"},           # prospects, brief, none (the agentic recipe)
        "prompt": {"type": "Text", "analyzer": "english", "nullable": True},  # Claude-Desktop template
        "last_done": {"type": "String", "nullable": True},   # ISO date last ticked
        "active": {"type": "Boolean"},
        "notes": {"type": "Text", "analyzer": "english", "nullable": True},
        "created": {"type": "String"},
    },
}

# The journal (dated rolling-memory diary) was retired into the documents store
# (docs/25, `noted_on` = the diary axis); see .ai/tasks/15 Phase 2d.

# chat_messages — the assistant's conversations, one row per message (docs/16).
# App state, not prediction: stored in Aito so history is durable across
# devices/restarts without a container filesystem. Append/replace per
# conversation via _delete + batch (no full-table rewrite). title/updated are
# denormalized onto each row so listing needs one query.
CHAT_MESSAGES = {
    "type": "table",
    "columns": {
        "message_id": {"type": "String"},
        "conversation_id": {"type": "String"},
        "seq": {"type": "Int"},                              # order within the conversation
        "role": {"type": "String"},                          # user | assistant
        "content": {"type": "Text", "analyzer": "english"},
        "trace": {"type": "Text", "nullable": True},         # JSON tool-trace (assistant turns)
        "title": {"type": "Text", "analyzer": "english"},    # conversation title (denormalized)
        "updated": {"type": "String"},                       # conversation updated epoch-ms (denormalized; string avoids Int range)
        "created": {"type": "String"},
    },
}

# changelog — an append-only audit of what changed: items created and updated
# (a todo done, a deal won/lost). One row per event. App
# state, so excluded from the CSV load/export machinery. Feeds "what changed"
# and, later, auto-generated notes for the assistant. See docs/22.
CHANGELOG = {
    "type": "table",
    "columns": {
        "change_id": {"type": "String"},
        "at": {"type": "String"},                             # ISO datetime, UTC
        "entity": {"type": "String"},                         # todo|deal|touch|routine|…
        "entity_id": {"type": "String"},
        "action": {"type": "String"},                         # created|updated|done|archived|won|lost|logged|…
        "summary": {"type": "Text", "analyzer": "english"},   # one human line
        "detail": {"type": "Text", "analyzer": "english", "nullable": True},  # JSON of what changed
    },
}

# documents — the knowledge store (docs/25): the operator's own writing,
# tagged and linked, kept in the tool. A first-class collection (the read-only
# file "Library" it replaces staged files into `search_docs`; documents are
# real rows, so search unions them directly). The write path mirrors the
# a full-table rewrite (log.add_document / update / delete), never `_modify`.
DOCUMENTS = {
    "type": "table",
    "columns": {
        "doc_id": {"type": "String"},
        "title": {"type": "Text", "analyzer": "english"},
        "body": {"type": "Text", "analyzer": "english"},        # markdown
        "kind": {"type": "String"},                             # DOC_KINDS
        "area": {"type": "String", "nullable": True},           # DOCUMENT_AREAS (fixed enum), optional
        # free-form ';'-joined topics — the arbitrary-topic axis `area` can't
        # cover (.ai/tasks/15 Phase 2); mirrors journal.tags' encoding.
        "topics": {"type": "String", "nullable": True},
        # the date the note is ABOUT — the diary / browse-by-day axis (distinct
        # from `created`, the row's write time). Null for a durable note that
        # isn't tied to a day; set for a daily-diary entry (.ai/tasks/15 Phase 2).
        "noted_on": {"type": "String", "nullable": True},
        "company": {"type": "String", "nullable": True},        # display string (kept)
        # first-class link to the company entity (derived: slug of `company`);
        # nullable because a document need not be about a company. So notes hang
        # off the same company node as its contacts/deals/touches (.ai/tasks/15).
        "company_id": {"type": "String", "nullable": True, "link": "companies.company_id"},
        "stakeholder_id": {"type": "String", "nullable": True},  # optional contact link
        "source": {"type": "String", "nullable": True},         # provenance (imported file path)
        "created": {"type": "String"},
        "updated": {"type": "String"},
    },
}

# users — the people using the app (docs/27). From a one-person company to a
# small team: the operator plus, e.g., an SDR. `assignee` on contacts/todos/
# deals points here (a plain String, validated on write). Auth is NOT here — the
# app reads the signed-in identity from Entra Easy Auth; this table maps that
# email to a name + role.
USERS = {
    "type": "table",
    "columns": {
        "user_id": {"type": "String"},
        "name": {"type": "Text", "analyzer": "english"},
        "email": {"type": "String"},        # matches the Easy Auth identity (lowercased)
        "role": {"type": "String"},          # USER_ROLES
        "active": {"type": "Boolean"},
        "created": {"type": "String"},
    },
}

# assignments — who owns which work item (docs/27). A join table, NOT a column
# on contacts/deals/todos: on this v2 build an in-place `_modify` update is
# unreliable and `contacts` can't be rewritten (touches links into it), so
# owning the assignment in its own small collection keeps the big/linked CRM
# tables untouched. It is written by the proven full-rewrite (the table is
# small); "my work" joins it back onto the entities. App-state (env-snapshot
# backed up), so it is outside the CSV seed/export machinery like search_*.
ASSIGNMENTS = {
    "type": "table",
    "columns": {
        "assignment_id": {"type": "String"},
        "entity": {"type": "String"},       # ASSIGNABLE_ENTITIES
        "entity_id": {"type": "String"},
        "user_id": {"type": "String"},
        "created": {"type": "String"},
    },
}

ASSIGNABLE_ENTITIES = {"contacts", "todos", "deals"}

# tokens — named bearer tokens for the remote MCP (docs/26, docs/28). We store
# only a SHA-256 of the secret (never the plaintext) plus a short prefix for
# display; the secret is shown once at creation and never again. App-state, so
# outside the CSV seed/export machinery — and never in the repo (real secrets).
TOKENS = {
    "type": "table",
    "columns": {
        "token_id": {"type": "String"},
        "label": {"type": "Text", "analyzer": "english"},
        "token_hash": {"type": "String"},   # sha256 hex of the secret
        "prefix": {"type": "String"},        # first 8 chars, for identification
        "created": {"type": "String"},
        "active": {"type": "Boolean"},
    },
}

# search_items is a v2 union VIEW (not a table) that merges contacts/deals/
# journal/documents behind one searchable `content` column — search.py declares
# and refreshes it (docs/24). No materialised rows to maintain, so it's not in
# TABLES and the `_modify` write bugs never touch it. Documents are a real
# collection now, so the view unions them directly (no staging table).
SEARCH_KINDS = {"doc", "contact", "deal"}

# search_contexts — one row per search served: the query, an optional anchor
# item (the selected item, "more like this"), and where it came from. The
# context half of the impressions loop (docs/23). App state, built at serve time.
SEARCH_CONTEXTS = {
    "type": "table",
    "columns": {
        "context_id": {"type": "String"},
        "query": {"type": "Text", "analyzer": "english"},
        # plain strings, not links: search_items is rebuilt wholesale (the index),
        # and Aito refuses to drop a table that's linked *into*. The ranking needs
        # only the impression→context link (for the query text), so items stay
        # rebuildable.
        "anchor_item_id": {"type": "String", "nullable": True},
        "source": {"type": "String"},                          # dashboard|assistant|mcp
        "at": {"type": "String"},                              # ISO datetime, UTC
    },
}

# search_impressions — the event/training table: one row per item shown for a
# context, with whether it was clicked (and room for more KPIs). Aito learns the
# ranking from these — `$p(clicked | context, item, match)` — the learning half
# of the loop (docs/23, A+C). Links let the ranking read context_id.query and
# item_id.text. App state; impressions are logged server-side on serve, clicks
# recorded by the dashboard + MCP (the in-app assistant never writes).
SEARCH_IMPRESSIONS = {
    "type": "table",
    "columns": {
        "impression_id": {"type": "String"},
        # context_id is a plain string, NOT a link: a v2 `_modify` update no-ops
        # on a collection that has a link (engine bug, docs/24), and record_click
        # updates `clicked` in place. So the query is denormalised onto the
        # impression (`query`) — the learned ranking reads it directly, no link
        # needed. search_contexts still keeps the anchor/source record.
        "context_id": {"type": "String"},
        "query": {"type": "Text", "analyzer": "english"},      # denormalised from the context
        "item_id": {"type": "String"},
        "position": {"type": "Int"},                           # 0-based rank when shown
        "clicked": {"type": "Boolean"},
        "at": {"type": "String"},                              # ISO datetime, UTC
    },
}

# search_vectors — one embedding per search_items row, for semantic / cross-
# lingual retrieval (docs/23). Built (embedded) at *reindex* time by
# search.build_index, NOT in TABLES and NOT on every write — embedding every
# item on each source write would be far too costly for the view-refresh model.
# `$nearest` over `vec` retrieves by cosine; Aito owns the ranking (rule 2). The
# dimension is 1000: text-embedding-3-large's native 3072 is requested down to
# 1000 via the API `dimensions` param (Matryoshka — quality is retained), because
# this Aito build caps a Vector column at 1017 dimensions (probed 2026-08-15;
# 1018 fails "buffer begin"). Changing the model/dim means changing this and
# reindexing.
EMBED_DIM = 1000
SEARCH_VECTORS = {
    "type": "table",
    "columns": {
        "item_id": {"type": "String"},                         # "kind:source_id"
        "kind": {"type": "String"},                            # SEARCH_KINDS (post-filter)
        "source_id": {"type": "String"},
        "title": {"type": "String"},                           # denormalised, for vector-only hits
        "vec": {"type": "Vector", "dimensions": EMBED_DIM, "similarity": "cosine"},
    },
}

# Creation order matters: touches links to contacts; posts denormalize from
# materials + channels (load those first).
TABLES = {
    "users": USERS, "assignments": ASSIGNMENTS, "tokens": TOKENS,
    # companies before contacts/deals — it is their `company_id` link target.
    "companies": COMPANIES,
    "contacts": CONTACTS, "touches": TOUCHES, "decisions": DECISIONS,
    "sessions": SESSIONS, "materials": MATERIALS, "channels": CHANNELS,
    "posts": POSTS, "todos": TODOS, "deals": DEALS, "experiments": EXPERIMENTS,
    "events": EVENTS, "routines": ROUTINES, "documents": DOCUMENTS,
    "chat_messages": CHAT_MESSAGES,
    "changelog": CHANGELOG,
    "search_contexts": SEARCH_CONTEXTS, "search_impressions": SEARCH_IMPRESSIONS,
}

SEGMENTS = {"accounting", "erp", "ecommerce", "analytics", "consultancy", "other"}
TIERS = {"A", "B", "C"}
LIFECYCLES = {"none", "announced", "shipped", "operating"}
SOURCES = {"warm", "trigger", "cold", "referral"}
WINDOWS = {"0800", "1215", "1600", "other"}
TOUCH_CHANNELS = {"call", "email", "linkedin", "meeting"}
OUTCOMES = {
    "no_answer",
    "callback_requested",
    "conversation",
    "meeting_booked",
    "declined",
    "bounced",
    "reply",
    "no_reply",
}
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DECISION_TYPES = {"call_priority", "opener_choice", "followup_timing"}
HUMAN_ACTIONS = {"accepted", "overridden", "ignored"}

# Experiments (the Build-Measure-Learn loop). Areas follow the startup-funnel
# canon (AARRR) so an experiment ties to the funnel metric it means to move.
EXPERIMENT_AREAS = {"acquisition", "activation", "revenue", "retention", "referral"}
EXPERIMENT_TYPES = {"landing_page", "pricing", "onboarding", "outreach", "content", "feature"}
EXPERIMENT_EFFORTS = {"small", "medium", "large"}
# terminal = validated/invalidated/inconclusive (a real verdict); running =
# in flight; abandoned = killed before a verdict (no validated learning).
EXPERIMENT_STATUS = {"running", "validated", "invalidated", "inconclusive", "abandoned"}
EXPERIMENT_TERMINAL = {"validated", "invalidated", "inconclusive"}


# routines enums (recurring agentic tasks)
ROUTINE_CADENCE = {"daily", "weekly", "monthly"}
ROUTINE_PREP = {"prospects", "brief", "none"}  # the agentic prep recipe

# users (docs/27): the operator has the run of the place; an sdr gets the
# read + safe-writes surface once role enforcement lands (parked Phase 2).
USER_ROLES = {"operator", "sdr"}

# documents (docs/25): kind is the top-level split (shareable reference vs
# private thinking); area is the optional, shared taxonomy.
DOC_KINDS = {"docs", "internal"}
DOCUMENT_AREAS = {"sales", "marketing", "operations", "rnd"}


# events-to-attend enums (the go/no-go lifecycle)
EVENT_TYPES = {"conference", "meetup", "webinar", "talk", "demo", "sponsor", "other"}
EVENT_STATUS = {"candidate", "go", "no_go", "attended"}
EVENT_TERMINAL = {"no_go", "attended"}      # a settled decision
EVENT_OUTCOMES = {"worthwhile", "neutral", "waste"}  # graded after attending


def experiment_validated(status: str) -> bool | None:
    if status == "validated":
        return True
    if status == "invalidated":
        return False
    return None  # running / inconclusive / abandoned — no clean bit yet


def confidence_bucket(confidence: float) -> str:
    if confidence < 0.4:
        return "low"
    if confidence <= 0.7:
        return "medium"
    return "high"

# sessions enums (website funnel)
WEB_SOURCES = {"organic", "paid_search", "social", "referral", "direct"}
DEVICES = {"desktop", "mobile", "tablet"}
LANDING_PAGES = {"/", "/pricing", "/docs", "/blog", "/demo"}

# deals enums (the sales pipeline)
DEAL_OPEN_STAGES = {"lead", "qualified", "demo", "pilot", "negotiation"}
DEAL_CLOSED_STAGES = {"closed_won", "closed_lost"}
DEAL_STAGES = DEAL_OPEN_STAGES | DEAL_CLOSED_STAGES | {"parked"}
DEAL_BLOCKERS = {
    "none", "consultant_lock", "timing_mismatch", "demo_readiness",
    "budget", "parked_intent", "no_champion",
}


def deal_won(stage: str) -> bool | None:
    """The predictor target: won/lost/open from the stage."""
    assert stage in DEAL_STAGES, f"unknown deal stage {stage!r}"
    if stage == "closed_won":
        return True
    if stage == "closed_lost":
        return False
    return None  # still open (or parked)


# todos enums (the action source)
# one action table; `area` routes a todo to its view. operations is the
# catch-all for work that doesn't belong to a named area.
TODO_AREAS = {"sales", "marketing", "operations", "rnd", "experiments"}
TODO_DEFAULT_AREA = "operations"
TODO_STATUS = {"ready", "draft", "prog", "blocked", "done", "monitor", "on_track",
               "review", "archived"}
# "review" = an agent finished and handed the work back for a human check. NOT
# terminal: agent-completed work stays on the worklist until a person closes it,
# so nothing self-certifies as done on work nobody looked at.
# `role` and `owner` are slugs, not enums — which lanes and which agent
# instances exist is deployment-specific. The shape is still validated (rule 3):
# lowercase alphanumerics, dots, dashes, underscores.
SLUG_PATTERN = r"[a-z0-9][a-z0-9._-]*"
# terminal states: excluded from the open worklist and exempt from the open-todo
# invariants. "done" is completed history; "archived" is abandoned (dropped, not
# finished, and — unlike done — it advances nothing). See docs/12.
TERMINAL_STATUSES = {"done", "archived"}
# `review` carries a promise: that a reviewer can check the work without mining
# the whole `detail` for it. The agent brief makes a HANDOFF block mandatory for
# exactly that reason, and on 2026-08-31 only 4 of 83 review items had one — the
# queue had grown to 266,000 characters with no summary layer, which is what made
# it unreviewable. A convention 95% ignore is a wish, so it is now checked.
# R&D only: `review` in the other areas is not the agent-lane handoff.
HANDOFF_MARKER = "=== HANDOFF ==="
HANDOFF_FIELDS = ("CLAIM:", "VERIFY:", "SCOPE:", "RISK:", "PUSHED:")
HANDOFF_AREAS = {"rnd"}


def handoff_problem(area: str, status: str, detail: str | None) -> str | None:
    """Why this row may not enter `review`, or None if it may.

    Checked on the RESULTING row, so one call may set `detail` and `status`
    together. Requires all five fields, not just the marker: a block with the
    header and nothing under it is the gesture, not the summary."""
    if status != "review" or area not in HANDOFF_AREAS:
        return None
    text = detail or ""
    if HANDOFF_MARKER not in text:
        return (f"status='review' needs a {HANDOFF_MARKER} block at the end of `detail` "
                f"(fields: {', '.join(HANDOFF_FIELDS)}). See strategy/v2-agent-brief.md. "
                f"If you cannot write the CLAIM line, the work is not finished.")
    body = text.split(HANDOFF_MARKER, 1)[1]
    missing = [f for f in HANDOFF_FIELDS if f not in body]
    if missing:
        return (f"the {HANDOFF_MARKER} block is missing {', '.join(missing)}. "
                f"All of {', '.join(HANDOFF_FIELDS)} are required — RISK especially: "
                f"the most useful lines in this queue have been the ones admitting "
                f"what was left unanswered.")
    return None
PREP_STATUS = {"prep_needed", "ready", "in_progress", "blocked", "n_a"}
LINKED_TYPES = {"contact", "deal", "asset", "instance", "workstream"}
# the kind of action, independent of area (what you physically do). "none" for
# items with no specific verb (a workstream, a standing item).
ACTION_TYPES = {"call", "email", "meeting", "message", "research", "admin",
                "post", "ship", "none"}
# areas whose work is time-driven (calendar lens) vs priority-driven (pipeline)
CALENDAR_AREAS = {"sales", "marketing"}
PIPELINE_AREAS = {"operations", "rnd", "experiments"}
# areas where a due_date is OPTIONAL (allowed, not required): operations work
# often has deadlines (renewals, reports), but plenty is just ongoing. Sales/
# marketing require a date; rnd/experiments forbid one; operations is in
# between — priority-ranked by default, datable when there's a deadline.
DEADLINE_AREAS = {"operations"}

# marketing enums (materials, channels, posts / messaging formula)
MATERIAL_TYPES = {"blog", "whitepaper", "demo", "video", "talk", "thread", "note", "other"}
# a channel rolls up to one of these platforms; the scorer predicts per platform.
PLATFORMS = {"linkedin", "hackernews", "reddit", "blog"}
POST_CHANNELS = PLATFORMS  # back-compat alias (some call sites/tests still say channel)
POST_STATUS = {"planned", "go", "no_go", "posted"}  # the go/no-go lifecycle
TONES = {"narrate", "announce", "explainer", "builder"}
AI_MADE = {"manual", "ai-assisted", "ai"}
POST_FORMATS = {"text", "link", "demo-link", "thread", "show-hn"}
LINK_PLACEMENTS = {"comment", "body", "n_a"}
LANES = {"warm", "cold"}
POST_TOPICS = {
    "agent_inference", "positioning", "product", "customer_proof",
    "oss_tool", "core_product",
}
POST_OUTCOMES = {"flop", "modest", "win"}


def post_length_bucket(length_chars: int) -> str:
    if length_chars < 250:
        return "short"
    if length_chars <= 450:
        return "medium"
    return "long"


def post_won(status: str, outcome: str | None) -> bool | None:
    """The scorer target: a posted post that won. Null while planned/go/no_go
    or before the outcome is measured."""
    if status != "posted" or not outcome:
        return None
    return outcome == "win"

# KPI label definitions: each maps an outcome to a boolean. Deterministic
# relabelings of the outcome enum (data prep, not inference); the rates,
# causes, and levers built on them all come from Aito. analytics.py reads
# these.
GOOD_OUTCOMES = {"conversation", "meeting_booked", "callback_requested"}
NOT_REACHED = {"no_answer", "no_reply", "bounced"}


def kpi_flags(outcome: str) -> dict[str, bool]:
    assert outcome in OUTCOMES, f"unknown outcome {outcome!r}"
    return {
        "good_outcome": outcome in GOOD_OUTCOMES,
        "reached": outcome not in NOT_REACHED,
        "booked": outcome == "meeting_booked",
    }


def contact_funnel_flags(outcomes: list[str]) -> dict[str, bool]:
    """The furthest sales-funnel stage a contact reached, from all of its
    touch outcomes. Monotone by construction (a meeting implies it was
    reached and touched). Empty list = an untouched contact."""
    flags = [kpi_flags(o) for o in outcomes]  # kpi_flags asserts each outcome
    return {
        "ever_touched": len(outcomes) > 0,
        "ever_reached": any(f["reached"] for f in flags),
        "ever_conversation": any(f["good_outcome"] for f in flags),
        "ever_meeting": any(f["booked"] for f in flags),
    }
