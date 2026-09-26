# Registered MCP tools


## who_to_call

params: ['top_n', 'window']
required: ['window']
Today's call queue for a window (0800, 1215, 1600), ranked by Aito's
    calibrated probability of a good outcome. Weak $p on small data is
    expected and shown as-is.

## opener_context

params: ['contact_id']
required: ['contact_id']
Evidence for drafting an opener: recent good-outcome touches of the
    contacts most similar to this one (Aito _similarity over segment, tier,
    ai_lifecycle), with their notes. The caller writes the opener.

## company_list

params: []
required: []
Every company (contacts rolled up by company, joined to their deals),
    each with its contact count, furthest sales-funnel stage, deal count, open
    deals, and open pipeline value. Sorted by open pipeline value, then size.
    There is no accounts table — company is a string; this is the rollup.

## search

params: ['kind', 'query', 'top_n']
required: ['query']
Smart search over content — a unified index of docs, contacts, and deals,
    ranked by Aito relevance and trained by clicks. Optionally restrict to one
    kind (doc/contact/deal). Grounds RAG: find the items, then read the source.
    Returns a `context_id`; pass it to record_click when a result proves useful,
    so the ranking learns. Builds the index if empty.

## record_click

params: ['context_id', 'item_id']
required: ['context_id', 'item_id']
Record that a search result was useful — the training signal for the
    ranking. `context_id` comes from a prior `search` call, `item_id` from one of
    its hits. Clicks lift that item for similar queries next time (docs/23).

## reindex_search

params: []
required: []
Rebuild the smart-search index from the current data (docs, contacts,
    deals). Run after loading or changing data so search reflects it.

## what_changed

params: []
required: []
Touches since yesterday plus open follow-ups due within 72h,
    due-first. Follow-ups go at the top of the brief.

## add_contact

params: ['ai_lifecycle', 'company', 'country', 'email_present', 'name', 'notes_tags', 'phone_present', 'role', 'segment', 'source', 'tier']
required: ['ai_lifecycle', 'company', 'country', 'email_present', 'name', 'phone_present', 'role', 'segment', 'source', 'tier']
Add a new person to the rolodex (writes to the live Aito instance).
    segment: accounting/erp/ecommerce/analytics/consultancy/other. tier: A/B/C.
    ai_lifecycle: none/announced/shipped/operating. source: warm/trigger/cold/
    referral. phone_present/email_present are booleans (the numbers themselves
    stay out of the data). Validated like a CSV load — bad enum values raise.

## add_deal

params: ['blocker', 'champion_present', 'company', 'probability', 'segment', 'stage', 'value_eur']
required: ['champion_present', 'company', 'probability', 'segment', 'stage', 'value_eur']
Add a new opportunity to the pipeline (writes to the live Aito
    instance). stage: lead/qualified/demo/pilot/negotiation/closed_won/
    closed_lost/parked. probability is the operator's own 0–100 estimate.
    blocker: none/consultant_lock/timing_mismatch/demo_readiness/budget/
    no_champion. `won` is derived from the stage.

## add_todo

params: ['action_type', 'area', 'due_date', 'linked_id', 'linked_type', 'owner', 'prep_status', 'priority', 'role', 'stakeholder_id', 'status', 'title', 'window']
required: ['area', 'priority', 'title']
Add an action to the todos table (live Aito). area: sales/distribution/
    operations/rnd/experiments (operations is the catch-all). priority
    1=highest. Sales/distribution need a due_date (ISO) + window; the others
    must not. action_type: call/email/meeting/message/research/admin/post/ship.
    A todo may link a deal (linked_type='deal', linked_id=<deal_id>) and a
    stakeholder (stakeholder_id=<contact_id>); both are validated live.
    `role` routes the work to a lane (a repo slug such as 'aito-core', a
    surface, or 'operator') — it is what an agent filters its queue on, so set
    it on anything an agent should pick up. `owner` names ONE agent instance
    inside that lane ('core-a'), for a role run by several agents: assignment
    is up front, because there is no safe self-service claim on this instance
    (see docs/12). Leave it null for a lane worked by a single agent.

    When an agent finishes, it sets status='review', not 'done' — a person
    closes the todo, so agent work does not self-certify.

## routines_board

params: []
required: []
The recurring routines with their due-state (which are due/overdue now).
    Computed from each routine's cadence and last_done.

## prepare_routine

params: ['routine_id']
required: ['routine_id']
Run a routine's prep: returns Aito-grounded data + a prompt to run here.
    e.g. a `prospects` routine (Monday outreach prep) returns the ranked
    candidate contacts and a prompt to draft openers and build the batch. The
    prep gathers; you (this session) execute via the MCP tools.

## tick_routine

params: ['routine_id']
required: ['routine_id']
Mark a routine done for the current period (stamps last_done).

## run_routine

params: ['force', 'routine_id']
required: ['routine_id']
Run a routine now: execute its prepared prompt through the assistant's
    bounded, read-only tool loop, record the narration as a dated document (the
    diary lane, docs/25), and tick the routine. This is the auto-run executor
    (docs/18) fired on demand rather than by the OS timer. `force=True` (default)
    runs it even if it isn't due; `force=False` skips a not-due routine (returns
    ran=None). It narrates and records — it does not act (no outbound; parked).

## add_event

params: ['cost_eur', 'location', 'name', 'notes', 'starts', 'type']
required: ['name', 'starts', 'type']
Record an event to attend as a candidate (live Aito). type: conference/
    meetup/webinar/talk/demo/sponsor/other; starts is an ISO date. The go/no-go
    decision is made later via decide_event.

## decide_event

params: ['event_id', 'notes', 'outcome', 'status']
required: ['event_id', 'status']
The go/no-go on an event (live Aito). status: go / no_go / attended (or
    back to candidate). An attended event may carry an outcome
    (worthwhile/neutral/waste).

## update_todo

params: ['changes', 'todo_id']
required: ['changes', 'todo_id']
Edit an existing todo (live Aito). `changes` maps field→value for any of
    area, title, action_type, status, priority, due_date, window, linked_id,
    linked_type, stakeholder_id, prep_status, detail. Each is validated; the
    calendar/pipeline due-date invariant is re-checked.

## classify_todo

params: ['given', 'title']
required: ['title']
Suggest a new todo's blank fields from its title: Aito predicts `area`
    and `action_type` (with calibrated $p) from the title's words, and a
    literal scan offers candidate stakeholders (contacts named/companied in
    the title). Advisory — confirm before add_todo; weak on thin data.

## add_material

params: ['ai_made', 'lane', 'length_chars', 'title', 'topic', 'type']
required: ['ai_made', 'lane', 'length_chars', 'title', 'topic', 'type']
Add a content artifact to the materials catalog (live Aito). type:
    blog/whitepaper/demo/video/talk/thread/note/other; lane: warm/cold;
    ai_made: manual/ai-assisted/ai.

## add_channel

params: ['name', 'platform']
required: ['name', 'platform']
Add a destination to the channels catalog (live Aito). name e.g.
    'r/programming'; platform: linkedin/hackernews/reddit/blog.

## add_post

params: ['channel_id', 'format', 'link_placement', 'material_id', 'status', 'tone']
required: ['channel_id', 'format', 'link_placement', 'material_id', 'tone']
Plan a post: a material posted to a channel, with a go/no-go status
    (planned/go/no_go/posted). KPIs arrive via log_post_result once posted.
    tone: narrate/announce/explainer/builder; link_placement: comment/body/n_a.
    The material's/channel's attributes denormalize in (validated live).

## log_post_result

params: ['outcome', 'post_id', 'reach_or_views', 'trials', 'upvotes']
required: ['outcome', 'post_id', 'reach_or_views']
Mark a planned post posted and record its KPIs (the measure step).
    outcome: flop/modest/win; the per-platform metric is reach/views, never
    upvotes. Re-derives `won`.

## log_session

params: ['campaign', 'converted_paid', 'country', 'device', 'landing_page', 'signed_up', 'source', 'started_trial']
required: ['converted_paid', 'country', 'device', 'landing_page', 'signed_up', 'source', 'started_trial']
Log a website session to the acquisition funnel (live Aito). source:
    organic/paid_search/social/referral/direct; device: desktop/mobile/tablet.
    Stages are monotone: converted_paid implies started_trial implies
    signed_up (enforced).

## log_touch

params: ['channel', 'contact_id', 'next_action', 'next_action_due', 'notes', 'outcome', 'window']
required: ['channel', 'contact_id', 'outcome', 'window']
Log a contact attempt or event. Channels: call, email, linkedin,
    meeting. Outcomes: no_answer, callback_requested, conversation,
    meeting_booked, declined, bounced, reply, no_reply. The logged touch
    immediately affects the next brief.

## deal_pipeline

params: []
required: []
The open sales pipeline ranked by weighted value (value × the
    operator's probability), with KPIs (weighted pipeline, open value,
    stalled count) and, per deal, Aito's calibrated close-likelihood
    (P(won) learned from closed-deal history) with its $why, plus a
    stalled flag. Where Aito's p_win diverges from the operator's own
    probability is the signal to look at.

## who_to_reach

params: ['top_n']
required: []
Who to reach at companies with a STALLED deal, the deals ranked by Aito's
    close-likelihood — a close-able deal gone quiet is the priority to unstick,
    and this returns the people to call at each. Traverses the company entity
    graph (contacts → companies ← deals) in one relational pass, so it answers a
    question that used to be a hand-joined three-read: 'who do I call to move the
    deals most worth saving?'

## complete_todo

params: ['champion_present', 'deal_blocker', 'deal_probability', 'deal_stage', 'todo_id']
required: ['todo_id']
Mark a todo done and, if it links to a deal, advance that deal in one
    step — the closed loop. After a sales call resolves, complete its todo
    and pass the deal changes the call implies (deal_stage moved, blocker
    cleared); the pipeline re-ranks immediately. Omit the deal_* args to
    just close the todo. Returns the updated todo and deal.

## claim_todo

params: ['agent', 'todo_id']
required: ['agent', 'todo_id']
Claim a todo for yourself BEFORE working it, so two agents never pick the
    same one. `agent` is your instance id — a lowercase slug that becomes the
    todo's `owner` (e.g. 'core-a'). RAISES if another agent already owns it; catch
    that and move to the next candidate. Idempotent if you already own it.

    Eager-claim loop for a lane's shared queue (docs/12): list your lane with
    todos_area / todos_now, filter to `role` == your lane with an empty `owner`,
    claim the top one with this, and on a failure try the next — no polling, no
    coordinating. Claiming only sets the owner; it does not start or finish the
    work. When you finish, set status='review' (a human closes it with
    complete_todo — agents don't self-certify).

## archive_todo

params: ['todo_id']
required: ['todo_id']
Archive (abandon) a todo: a terminal state separate from done. Use it to
    drop an action you're no longer going to do — it disappears from the open
    lenses but, unlike complete_todo, advances nothing (no deal move, no
    outcome). Returns the updated todo.

## recent_changes

params: ['entity', 'limit']
required: []
The change log: items created/updated across the system (a todo done, a
    deal won/lost), newest first. Optionally filter to one
    entity kind (todo/deal/routine/…). Read-only — the raw material for
    daily/weekly note roll-ups.

## create_backup

params: ['kind']
required: []
Snapshot the database before a risky change — a copy-on-write Aito env
    (milliseconds, ~no disk; docs/21). Use kind='tx' before a bulk edit (keeps
    the last 16); 'daily' keeps 7. Restoring is deliberately operator-only
    (`company-ai restore`), never from here. Returns the snapshot created and
    any rotated out.

## log_deal_update

params: ['blocker', 'champion_present', 'deal_id', 'probability', 'stage']
required: ['deal_id']
Advance a deal — the closed loop from the action surface. After a
    call resolves (meeting booked, stage moved, blocker cleared, deal
    closed_won/closed_lost), update it here; the pipeline re-ranks and the
    risk model re-derives immediately. stage: lead/qualified/demo/pilot/
    negotiation/closed_won/closed_lost/parked.

## log_decision

params: ['agent_confidence', 'chosen', 'context', 'decision_type', 'human_action', 'human_alternative']
required: ['agent_confidence', 'chosen', 'context', 'decision_type', 'human_action']
Record what the agent recommended and what the human did.
    decision_type: call_priority, opener_choice, followup_timing.
    human_action: accepted, overridden, ignored. Log an override whenever
    the operator reorders or skips the recommended queue.

## segment_360

params: ['ai_lifecycle', 'segment', 'source', 'tier']
required: []
The 360 analysis for a segment slice: per KPI (conversion, reach,
    meetings) the rate with its $why, the within-segment root causes
    (_relate), and the lever that most moves it (_recommend). All
    dimensions optional; omit for the whole pipeline. The same data the
    dashboard renders.

## funnel

params: ['name', 'slice']
required: ['name']
A predictive funnel. name is 'website' (acquisition: visitor → signup
    → trial → paid, over sessions) or 'sales' (contact → touched → reached →
    conversation → meeting). `slice` filters by the funnel's dimensions
    (website: source/campaign/device/country/landing_page; sales: segment/
    tier/ai_lifecycle/source). Returns stage counts and step conversion, the
    biggest-drop leak, Aito's calibrated outlook for the deepest stage, the
    causes of the leak (_relate), and the lever that moves it (_recommend).

## documents_list

params: ['area', 'company', 'contact', 'kind', 'topic']
required: []
List the Documents (the knowledge store, docs/25) — the operator's
    strategy/plans/notes/reference the agent grounds on. Filter by kind
    (docs/internal), area (sales/marketing/operations/rnd), company, contact, or
    a free-form topic. Returns each document's id, title, kind, area, topics,
    noted_on (the day it's about, if any), and links (not the body).

## document_diary

params: ['company', 'since', 'topic', 'until']
required: []
The diary (docs/25): Documents dated to a day (`noted_on`), newest day
    first and grouped by day — the operator's daily notes. Optionally narrow to a
    company, a topic, or an ISO `[since, until]` date window. Returns days, each
    with its documents (id/title/topics/company/links, not the body).

## document_topics

params: []
required: []
The free-form topics across the Documents store, each with its document
    count (docs/25) — the browse-by-topic index. Feed a topic back to
    documents_list(topic=…) or document_diary(topic=…).

## document_read

params: ['doc_id']
required: ['doc_id']
Read one Document by its id (from documents_list). Returns its title,
    full markdown body, tags, and links — for grounding.

## add_document

params: ['area', 'body', 'company', 'kind', 'noted_on', 'stakeholder_id', 'title', 'topics']
required: ['body', 'title']
Write a Document to the knowledge store — content to keep and read back.
    kind is docs|internal; area optional (sales/marketing/operations/rnd);
    company/stakeholder_id optional links; topics a ';'-joined free-form list;
    noted_on the diary day (ISO) that files it in the diary. An unknown kind/area
    or a dangling contact raises (rule 3).

## update_document

params: ['changes', 'doc_id']
required: ['changes', 'doc_id']
Edit a Document. `changes` may set title/body/kind/area/company/
    stakeholder_id/topics/noted_on; stamps `updated`, and keeps the company entity
    link in step with `company`. Validated like a write (rule 3).

## remove_document

params: ['doc_id']
required: ['doc_id']
Delete a Document from the knowledge store.

## list_users

params: []
required: []
The team roster (docs/27): each user's id, name, email, role, active. Use
    the ids to `assign` work or read someone's `my_work`.

## assign

params: ['entity', 'entity_id', 'user_id']
required: ['entity', 'entity_id']
Assign a work item to a user (docs/27). `entity` is contacts|todos|deals;
    `user_id` from list_users, or omit/null to unassign. Ownership lives in a
    join table, so the CRM tables are untouched. Validated (rule 3).

## my_work

params: ['user_id']
required: ['user_id']
The contacts, todos, and deals assigned to a user (docs/27) — their
    focused lane over the shared CRM.

## todos_now

params: ['top_n']
required: []
The cross-area action surface: the most urgent open todos right now,
    ranked by overdue-ness, then priority, then due-date proximity. This is
    the 'Now' view and the action core of the morning brief — what to do
    next across sales, distribution, operations, and R&D.

## todos_area

params: ['area']
required: ['area']
Todos for one area. Sales and distribution come back laid out by date
    (the calendar lens); operations and R&D come back ranked by priority
    (the pipeline lens). area: sales, distribution, operations, rnd.

## score_post

params: ['features', 'platform']
required: ['platform']
Score a marketing draft before posting. platform is linkedin /
    hackernews / reddit / blog. `features` may include tone (narrate/
    announce/explainer/builder), ai_made (manual/ai-assisted/ai), format,
    link_placement (comment/body/n_a), lane, topic, length_bucket, weekday.
    Returns the predicted P(win) for the platform (LinkedIn=reach, HN=views,
    never upvotes), the platform base rate, the per-feature contribution
    ($why), and the lever switches that most raise the win probability.

## experiment_board

params: []
required: []
The Build-Measure-Learn board: the validated-learning rate, the status
    mix, the running bets, and — from Aito — which kinds of experiment tend to
    pay off (P(validated) by effort; small/cheap bets should validate more).
    Honest-weak with few decided experiments.

## add_experiment

params: ['area', 'baseline', 'effort', 'hypothesis', 'metric', 'target', 'type']
required: ['area', 'baseline', 'effort', 'hypothesis', 'metric', 'target', 'type']
Start an experiment (the Build step; status=running). area is an AARRR
    stage (acquisition/activation/revenue/retention/referral); type is
    landing_page/pricing/onboarding/outreach/content/feature; effort is
    small/medium/large; target is the metric value that would validate it.

## log_experiment_result

params: ['experiment_id', 'learning', 'result', 'status']
required: ['experiment_id', 'result', 'status']
Resolve a running experiment (the Learn step): record the measured
    result + the verdict (validated/invalidated/inconclusive) + the learning.
    Re-derives `validated` and re-ranks the board.

## decision_scorecard

params: []
required: []
The dogfood loop: how often the operator accepts the agent's
    recommendations (overall and by decision_type), and — the key question —
    whether the agent's confidence is trustworthy (Aito's P(accepted) by
    confidence bucket; it should climb low→high). Thin real data means weak,
    honest early numbers.

## predict

params: ['predict_field', 'table', 'where']
required: ['predict_field', 'table', 'where']
Generic escape hatch: ask Aito for the distribution of any field
    given any conditions, e.g. predict('touches', {'window': '0800'},
    'outcome'). Use linked fields like 'contact_id.segment' in where.
