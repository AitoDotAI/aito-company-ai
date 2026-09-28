"""MCP server: six tools, each a thin wrapper over one query or one write.

Registration (Claude Code):
  claude mcp add aito-company-ai -- uv --directory <repo path> run company-ai-mcp
"""

from datetime import date

from mcp.server.fastmcp import FastMCP

from . import analytics
from . import deals
from . import decisions
from . import experiments
from . import funnels
from . import log as logbook
from . import queries
from . import scorer
from . import todos
from .aito import AitoClient
from .config import Config

mcp = FastMCP("aito-company-ai")


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _embedder():
    """The embeddings callable for semantic search, or None if unconfigured."""
    from . import embed
    return embed.embedder(Config.from_env())


@mcp.tool()
def who_to_call(window: str, top_n: int = 5) -> list:
    """Today's call queue for a window (0800, 1215, 1600), ranked by Aito's
    calibrated probability of a good outcome. Weak $p on small data is
    expected and shown as-is."""
    return queries.who_to_call(_client(), window, top_n=top_n, as_of=date.today()).derived


@mcp.tool()
def opener_context(contact_id: str) -> list:
    """Evidence for drafting an opener: recent good-outcome touches of the
    contacts most similar to this one (Aito _similarity over segment, tier,
    ai_lifecycle), with their notes. The caller writes the opener."""
    return queries.opener_context(_client(), contact_id).derived


@mcp.tool()
def company_list() -> dict:
    """Every company (contacts rolled up by company, joined to their deals),
    each with its contact count, furthest sales-funnel stage, deal count, open
    deals, and open pipeline value. Sorted by open pipeline value, then size.
    There is no accounts table — company is a string; this is the rollup."""
    from . import companies
    return companies.roster(_client()).derived


@mcp.tool()
def search(query: str, kind: str | None = None, top_n: int = 10) -> dict:
    """Smart search over content — a unified index of docs, contacts, and deals,
    ranked by Aito relevance and trained by clicks. Optionally restrict to one
    kind (doc/contact/deal). Grounds RAG: find the items, then read the source.
    Returns a `context_id`; pass it to record_click when a result proves useful,
    so the ranking learns. Builds the index if empty."""
    from . import search as search_mod
    client = _client()
    return search_mod.serve(client, query, kind=kind, top_n=top_n, source="mcp",
                            embed=_embedder())


@mcp.tool()
def record_click(context_id: str, item_id: str) -> dict:
    """Record that a search result was useful — the training signal for the
    ranking. `context_id` comes from a prior `search` call, `item_id` from one of
    its hits. Clicks lift that item for similar queries next time (docs/23)."""
    from . import search as search_mod
    return search_mod.record_click(_client(), context_id, item_id)


@mcp.tool()
def reindex_search() -> dict:
    """Rebuild the smart-search index from the current data (docs, contacts,
    deals). Run after loading or changing data so search reflects it."""
    from . import search as search_mod
    return search_mod.build_index(_client(), embed=_embedder())


@mcp.tool()
def what_changed() -> dict:
    """Touches since yesterday plus open follow-ups due within 72h,
    due-first. Follow-ups go at the top of the brief."""
    return queries.what_changed(_client(), as_of=date.today()).derived


@mcp.tool()
def add_contact(
    name: str, company: str, role: str, segment: str, tier: str,
    ai_lifecycle: str, source: str, country: str,
    phone_present: bool, email_present: bool, notes_tags: list[str] | None = None,
) -> dict:
    """Add a new person to the rolodex (writes to the live Aito instance).
    segment: accounting/erp/ecommerce/analytics/consultancy/other. tier: A/B/C.
    ai_lifecycle: none/announced/shipped/operating. source: warm/trigger/cold/
    referral. phone_present/email_present are booleans (the numbers themselves
    stay out of the data). Validated like a CSV load — bad enum values raise."""
    return logbook.add_contact(
        _client(), name=name, company=company, role=role, segment=segment,
        tier=tier, ai_lifecycle=ai_lifecycle, source=source, country=country,
        phone_present=phone_present, email_present=email_present, notes_tags=notes_tags)


@mcp.tool()
def add_deal(
    company: str, segment: str, stage: str, value_eur: int, probability: int,
    champion_present: bool, blocker: str = "none",
) -> dict:
    """Add a new opportunity to the pipeline (writes to the live Aito
    instance). stage: lead/qualified/demo/pilot/negotiation/closed_won/
    closed_lost/parked. probability is the operator's own 0–100 estimate.
    blocker: none/consultant_lock/timing_mismatch/demo_readiness/budget/
    no_champion. `won` is derived from the stage."""
    return logbook.add_deal(
        _client(), company=company, segment=segment, stage=stage,
        value_eur=value_eur, probability=probability,
        champion_present=champion_present, blocker=blocker)


@mcp.tool()
def add_todo(
    area: str, title: str, priority: int, status: str = "ready",
    prep_status: str = "ready", action_type: str | None = None,
    due_date: str | None = None, window: str | None = None,
    linked_id: str | None = None, linked_type: str | None = None,
    stakeholder_id: str | None = None, role: str | None = None,
    owner: str | None = None,
) -> dict:
    """Add an action to the todos table (live Aito). area: sales/distribution/
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
    closes the todo, so agent work does not self-certify."""
    return logbook.add_todo(
        _client(), area=area, title=title, priority=priority, status=status,
        prep_status=prep_status, action_type=action_type, due_date=due_date,
        window=window, linked_id=linked_id, linked_type=linked_type,
        stakeholder_id=stakeholder_id, role=role, owner=owner)


@mcp.tool()
def routines_board() -> dict:
    """The recurring routines with their due-state (which are due/overdue now).
    Computed from each routine's cadence and last_done."""
    from . import routines
    return routines.board(_client()).derived


@mcp.tool()
def prepare_routine(routine_id: str) -> dict:
    """Run a routine's prep: returns Aito-grounded data + a prompt to run here.
    e.g. a `prospects` routine (Monday outreach prep) returns the ranked
    candidate contacts and a prompt to draft openers and build the batch. The
    prep gathers; you (this session) execute via the MCP tools."""
    from . import routines
    match = [r for r in _client().query({"from": "routines", "limit": 10000})["hits"]
             if r["routine_id"] == routine_id]
    assert match, f"unknown routine_id {routine_id!r}"
    return routines.prepare(_client(), match[0]).derived


@mcp.tool()
def tick_routine(routine_id: str) -> dict:
    """Mark a routine done for the current period (stamps last_done)."""
    return logbook.tick_routine(_client(), routine_id)


@mcp.tool()
def run_routine(routine_id: str, force: bool = True) -> dict:
    """Run a routine now: execute its prepared prompt through the assistant's
    bounded, read-only tool loop, record the narration as a dated document (the
    diary lane, docs/25), and tick the routine. This is the auto-run executor
    (docs/18) fired on demand rather than by the OS timer. `force=True` (default)
    runs it even if it isn't due; `force=False` skips a not-due routine (returns
    ran=None). It narrates and records — it does not act (no outbound; parked)."""
    from . import routines
    return routines.run_routine(_client(), routine_id, force=force)


@mcp.tool()
def add_event(name: str, type: str, starts: str, location: str | None = None,
              cost_eur: int | None = None, notes: str | None = None) -> dict:
    """Record an event to attend as a candidate (live Aito). type: conference/
    meetup/webinar/talk/demo/sponsor/other; starts is an ISO date. The go/no-go
    decision is made later via decide_event."""
    return logbook.add_event(_client(), name=name, type=type, starts=starts,
                             location=location, cost_eur=cost_eur, notes=notes)


@mcp.tool()
def decide_event(event_id: str, status: str, outcome: str | None = None,
                 notes: str | None = None) -> dict:
    """The go/no-go on an event (live Aito). status: go / no_go / attended (or
    back to candidate). An attended event may carry an outcome
    (worthwhile/neutral/waste)."""
    return logbook.decide_event(_client(), event_id, status, outcome=outcome, notes=notes)


@mcp.tool()
def update_todo(todo_id: str, changes: dict | None = None,
                append_detail: str | None = None) -> dict:
    """Edit an existing todo (live Aito). `changes` maps field→value for any of
    area, title, action_type, status, priority, due_date, window, linked_id,
    linked_type, stakeholder_id, prep_status, detail, role, owner. Each is
    validated; the calendar/pipeline due-date invariant is re-checked.

    `changes["detail"]` REPLACES the whole detail. To add a section without
    rewriting it, pass `append_detail` instead: it is appended after a blank
    line, and concurrent appends from several agents all land.

    `owner`: `{"owner": ""}` RELEASES a claim; another agent can then
    claim_todo it. Release is NOT guarded: it clears whoever holds the todo.
    So release only your own claim, or one confirmed abandoned (its agent is
    gone, or a human said so); releasing a live agent's claim lets two agents
    work the same todo. Setting a DIFFERENT owner over a live claim raises
    ClaimTaken: a takeover is release-then-claim, two deliberate steps.

    Safe to call from several agents at once: only the changed fields of this
    one row are written, version-checked, so concurrent edits compose. Returns
    the todo as read back after the write; an error means it did not persist."""
    return logbook.update_todo(_client(), todo_id, changes or {}, append_detail=append_detail)


@mcp.tool()
def classify_todo(title: str, given: dict | None = None) -> dict:
    """Suggest a new todo's blank fields from its title: Aito predicts `area`
    and `action_type` (with calibrated $p) from the title's words, and a
    literal scan offers candidate stakeholders (contacts named/companied in
    the title). Advisory — confirm before add_todo; weak on thin data."""
    from . import classify
    return classify.classify_todo(_client(), title, given).derived


@mcp.tool()
def add_material(type: str, title: str, topic: str, lane: str, ai_made: str,
                 length_chars: int) -> dict:
    """Add a content artifact to the materials catalog (live Aito). type:
    blog/whitepaper/demo/video/talk/thread/note/other; lane: warm/cold;
    ai_made: manual/ai-assisted/ai."""
    return logbook.add_material(_client(), type=type, title=title, topic=topic,
                                lane=lane, ai_made=ai_made, length_chars=length_chars)


@mcp.tool()
def add_channel(name: str, platform: str) -> dict:
    """Add a destination to the channels catalog (live Aito). name e.g.
    'r/programming'; platform: linkedin/hackernews/reddit/blog."""
    return logbook.add_channel(_client(), name=name, platform=platform)


@mcp.tool()
def add_post(material_id: str, channel_id: str, tone: str, format: str,
             link_placement: str, status: str = "planned") -> dict:
    """Plan a post: a material posted to a channel, with a go/no-go status
    (planned/go/no_go/posted). KPIs arrive via log_post_result once posted.
    tone: narrate/announce/explainer/builder; link_placement: comment/body/n_a.
    The material's/channel's attributes denormalize in (validated live)."""
    return logbook.add_post(
        _client(), material_id=material_id, channel_id=channel_id, tone=tone,
        format=format, link_placement=link_placement, status=status)


@mcp.tool()
def log_post_result(post_id: str, outcome: str, reach_or_views: int,
                    upvotes: int = 0, trials: int = 0) -> dict:
    """Mark a planned post posted and record its KPIs (the measure step).
    outcome: flop/modest/win; the per-platform metric is reach/views, never
    upvotes. Re-derives `won`."""
    return logbook.log_post_result(
        _client(), post_id=post_id, outcome=outcome, reach_or_views=reach_or_views,
        upvotes=upvotes, trials=trials)


@mcp.tool()
def log_session(
    source: str, landing_page: str, country: str, device: str,
    signed_up: bool, started_trial: bool, converted_paid: bool,
    campaign: str | None = None,
) -> dict:
    """Log a website session to the acquisition funnel (live Aito). source:
    organic/paid_search/social/referral/direct; device: desktop/mobile/tablet.
    Stages are monotone: converted_paid implies started_trial implies
    signed_up (enforced)."""
    return logbook.log_session(
        _client(), source=source, landing_page=landing_page, country=country,
        device=device, signed_up=signed_up, started_trial=started_trial,
        converted_paid=converted_paid, campaign=campaign)


@mcp.tool()
def log_touch(
    contact_id: str,
    channel: str,
    window: str,
    outcome: str,
    next_action: str | None = None,
    next_action_due: str | None = None,
    notes: str | None = None,
) -> dict:
    """Log a contact attempt or event. Channels: call, email, linkedin,
    meeting. Outcomes: no_answer, callback_requested, conversation,
    meeting_booked, declined, bounced, reply, no_reply. The logged touch
    immediately affects the next brief."""
    return logbook.log_touch(
        _client(), contact_id, channel, window, outcome,
        next_action=next_action, next_action_due=next_action_due, notes=notes,
    )


@mcp.tool()
def deal_pipeline() -> dict:
    """The open sales pipeline ranked by weighted value (value × the
    operator's probability), with KPIs (weighted pipeline, open value,
    stalled count) and, per deal, Aito's calibrated close-likelihood
    (P(won) learned from closed-deal history) with its $why, plus a
    stalled flag. Where Aito's p_win diverges from the operator's own
    probability is the signal to look at."""
    return deals.pipeline(_client()).derived


@mcp.tool()
def who_to_reach(top_n: int = 10) -> dict:
    """Who to reach at companies with a STALLED deal, the deals ranked by Aito's
    close-likelihood — a close-able deal gone quiet is the priority to unstick,
    and this returns the people to call at each. Traverses the company entity
    graph (contacts → companies ← deals) in one relational pass, so it answers a
    question that used to be a hand-joined three-read: 'who do I call to move the
    deals most worth saving?'"""
    return deals.who_to_reach(_client(), top_n=top_n).derived


@mcp.tool()
def complete_todo(
    todo_id: str,
    deal_stage: str | None = None,
    deal_probability: int | None = None,
    deal_blocker: str | None = None,
    champion_present: bool | None = None,
) -> dict:
    """Mark a todo done and, if it links to a deal, advance that deal in one
    step — the closed loop. After a sales call resolves, complete its todo
    and pass the deal changes the call implies (deal_stage moved, blocker
    cleared); the pipeline re-ranks immediately. Omit the deal_* args to
    just close the todo. Returns the updated todo and deal."""
    return logbook.complete_todo(
        _client(), todo_id, deal_stage=deal_stage, deal_probability=deal_probability,
        deal_blocker=deal_blocker, champion_present=champion_present)


@mcp.tool()
def claim_todo(todo_id: str, agent: str) -> dict:
    """Claim a todo for yourself BEFORE working it, so two agents never pick the
    same one. `agent` is your instance id — a lowercase slug that becomes the
    todo's `owner` (e.g. 'core-a'). RAISES if another agent already owns it; catch
    that and move to the next candidate. Idempotent if you already own it.

    Eager-claim loop for a lane's shared queue (docs/12): list your lane with
    todos_area / todos_now, filter to `role` == your lane with an empty `owner`,
    claim the top one with this, and on a failure try the next — no polling, no
    coordinating. Claiming only sets the owner; it does not start or finish the
    work. When you finish, set status='review' (a human closes it with
    complete_todo — agents don't self-certify).

    To give a todo up, release it with update_todo(todo_id, {"owner": ""}); it
    is then claimable again. Freeing ANOTHER agent's claim the same way is for
    a claim confirmed abandoned, not a busy one (see update_todo)."""
    return logbook.claim_todo(_client(), todo_id, agent)


@mcp.tool()
def archive_todo(todo_id: str) -> dict:
    """Archive (abandon) a todo: a terminal state separate from done. Use it to
    drop an action you're no longer going to do — it disappears from the open
    lenses but, unlike complete_todo, advances nothing (no deal move, no
    outcome). Returns the updated todo."""
    return logbook.archive_todo(_client(), todo_id)


@mcp.tool()
def recent_changes(limit: int = 50, entity: str | None = None) -> dict:
    """The change log: items created/updated across the system (a todo done, a
    deal won/lost), newest first. Optionally filter to one
    entity kind (todo/deal/routine/…). Read-only — the raw material for
    daily/weekly note roll-ups."""
    from . import changelog
    return changelog.recent(_client(), limit=limit, entity=entity)


@mcp.tool()
def create_backup(kind: str = "tx") -> dict:
    """Snapshot the database before a risky change — a copy-on-write Aito env
    (milliseconds, ~no disk; docs/21). Use kind='tx' before a bulk edit (keeps
    the last 16); 'daily' keeps 7. Restoring is deliberately operator-only
    (`company-ai restore`), never from here. Returns the snapshot created and
    any rotated out."""
    import time
    from datetime import date
    from . import backups
    stamp = date.today().isoformat() if kind == backups.DAILY else str(int(time.time()))
    return backups.backup(_client(), kind, stamp)


@mcp.tool()
def log_deal_update(
    deal_id: str,
    stage: str | None = None,
    probability: int | None = None,
    blocker: str | None = None,
    champion_present: bool | None = None,
) -> dict:
    """Advance a deal — the closed loop from the action surface. After a
    call resolves (meeting booked, stage moved, blocker cleared, deal
    closed_won/closed_lost), update it here; the pipeline re-ranks and the
    risk model re-derives immediately. stage: lead/qualified/demo/pilot/
    negotiation/closed_won/closed_lost/parked."""
    return logbook.log_deal_update(
        _client(), deal_id, stage=stage, probability=probability,
        blocker=blocker, champion_present=champion_present)


@mcp.tool()
def log_decision(
    decision_type: str,
    context: dict,
    chosen: str,
    agent_confidence: float,
    human_action: str,
    human_alternative: str | None = None,
) -> dict:
    """Record what the agent recommended and what the human did.
    decision_type: call_priority, opener_choice, followup_timing.
    human_action: accepted, overridden, ignored. Log an override whenever
    the operator reorders or skips the recommended queue."""
    return logbook.log_decision(
        _client(), decision_type, context, chosen, agent_confidence,
        human_action, human_alternative=human_alternative,
    )


@mcp.tool()
def segment_360(
    segment: str | None = None,
    tier: str | None = None,
    ai_lifecycle: str | None = None,
    source: str | None = None,
) -> dict:
    """The 360 analysis for a segment slice: per KPI (conversion, reach,
    meetings) the rate with its $why, the within-segment root causes
    (_relate), and the lever that most moves it (_recommend). All
    dimensions optional; omit for the whole pipeline. The same data the
    dashboard renders."""
    slice_ = {"segment": segment, "tier": tier,
              "ai_lifecycle": ai_lifecycle, "source": source}
    return analytics.segment_360(_client(), slice_).derived


@mcp.tool()
def funnel(name: str, slice: dict | None = None) -> dict:
    """A predictive funnel. name is 'website' (acquisition: visitor → signup
    → trial → paid, over sessions) or 'sales' (contact → touched → reached →
    conversation → meeting). `slice` filters by the funnel's dimensions
    (website: source/campaign/device/country/landing_page; sales: segment/
    tier/ai_lifecycle/source). Returns stage counts and step conversion, the
    biggest-drop leak, Aito's calibrated outlook for the deepest stage, the
    causes of the leak (_relate), and the lever that moves it (_recommend)."""
    return funnels.funnel(_client(), name, slice or {}).derived


@mcp.tool()
def documents_list(kind: str | None = None, area: str | None = None,
                   company: str | None = None, contact: str | None = None,
                   topic: str | None = None) -> dict:
    """List the Documents (the knowledge store, docs/25) — the operator's
    strategy/plans/notes/reference the agent grounds on. Filter by kind
    (docs/internal), area (sales/marketing/operations/rnd), company, contact, or
    a free-form topic. Returns each document's id, title, kind, area, topics,
    noted_on (the day it's about, if any), and links (not the body)."""
    from . import documents
    docs = documents.feed(_client(), kind=kind, area=area, company=company,
                          contact=contact, topic=topic).derived["documents"]
    return {"documents": [{k: d.get(k) for k in
                           ("doc_id", "title", "kind", "area", "topics", "noted_on",
                            "company", "stakeholder_id", "contact_name", "updated")} for d in docs]}


@mcp.tool()
def document_diary(company: str | None = None, topic: str | None = None,
                   since: str | None = None, until: str | None = None) -> dict:
    """The diary (docs/25): Documents dated to a day (`noted_on`), newest day
    first and grouped by day — the operator's daily notes. Optionally narrow to a
    company, a topic, or an ISO `[since, until]` date window. Returns days, each
    with its documents (id/title/topics/company/links, not the body)."""
    from . import documents
    days = documents.diary(_client(), company=company, topic=topic,
                           since=since, until=until).derived["days"]
    return {"days": [{"day": g["day"],
                      "documents": [{k: d.get(k) for k in
                                     ("doc_id", "title", "topics", "company",
                                      "contact_name")} for d in g["documents"]]}
                     for g in days]}


@mcp.tool()
def document_topics() -> dict:
    """The free-form topics across the Documents store, each with its document
    count (docs/25) — the browse-by-topic index. Feed a topic back to
    documents_list(topic=…) or document_diary(topic=…)."""
    from . import documents
    return documents.topics(_client()).derived


@mcp.tool()
def document_read(doc_id: str) -> dict:
    """Read one Document by its id (from documents_list). Returns its title,
    full markdown body, tags, and links — for grounding."""
    from . import documents
    return documents.read(_client(), doc_id)


@mcp.tool()
def add_document(title: str, body: str, kind: str = "internal",
                 area: str | None = None, company: str | None = None,
                 stakeholder_id: str | None = None,
                 topics: str | None = None, noted_on: str | None = None) -> dict:
    """Write a Document to the knowledge store — content to keep and read back.
    kind is docs|internal; area optional (sales/marketing/operations/rnd);
    company/stakeholder_id optional links; topics a ';'-joined free-form list;
    noted_on the diary day (ISO) that files it in the diary. An unknown kind/area
    or a dangling contact raises (rule 3)."""
    return logbook.add_document(_client(), title=title, body=body, kind=kind,
                                area=area, company=company, stakeholder_id=stakeholder_id,
                                topics=topics, noted_on=noted_on)


@mcp.tool()
def update_document(doc_id: str, changes: dict) -> dict:
    """Edit a Document. `changes` may set title/body/kind/area/company/
    stakeholder_id/topics/noted_on; stamps `updated`, and keeps the company entity
    link in step with `company`. Validated like a write (rule 3)."""
    return logbook.update_document(_client(), doc_id, changes)


@mcp.tool()
def remove_document(doc_id: str) -> dict:
    """Delete a Document from the knowledge store."""
    return logbook.delete_document(_client(), doc_id)


@mcp.tool()
def list_users() -> dict:
    """The team roster (docs/27): each user's id, name, email, role, active. Use
    the ids to `assign` work or read someone's `my_work`."""
    from . import users
    return {"users": users.list_users(_client(), active_only=False)}


@mcp.tool()
def assign(entity: str, entity_id: str, user_id: str | None = None) -> dict:
    """Assign a work item to a user (docs/27). `entity` is contacts|todos|deals;
    `user_id` from list_users, or omit/null to unassign. Ownership lives in a
    join table, so the CRM tables are untouched. Validated (rule 3)."""
    return logbook.set_assignment(_client(), entity, entity_id, user_id)


@mcp.tool()
def my_work(user_id: str) -> dict:
    """The contacts, todos, and deals assigned to a user (docs/27) — their
    focused lane over the shared CRM."""
    from . import users
    return users.my_work(_client(), user_id).derived


@mcp.tool()
def todos_now(top_n: int = 8) -> dict:
    """The cross-area action surface: the most urgent open todos right now,
    ranked by overdue-ness, then priority, then due-date proximity. This is
    the 'Now' view and the action core of the morning brief — what to do
    next across sales, distribution, operations, and R&D."""
    return todos.now(_client(), top_n=top_n).derived


@mcp.tool()
def todos_area(area: str) -> dict:
    """Todos for one area. Sales and distribution come back laid out by date
    (the calendar lens); operations and R&D come back ranked by priority
    (the pipeline lens). area: sales, distribution, operations, rnd."""
    from . import schema
    client = _client()
    if area in schema.CALENDAR_AREAS:
        return todos.calendar(client, area).derived
    return todos.pipeline(client, area).derived


@mcp.tool()
def score_post(platform: str, features: dict | None = None) -> dict:
    """Score a marketing draft before posting. platform is linkedin /
    hackernews / reddit / blog. `features` may include tone (narrate/
    announce/explainer/builder), ai_made (manual/ai-assisted/ai), format,
    link_placement (comment/body/n_a), lane, topic, length_bucket, weekday.
    Returns the predicted P(win) for the platform (LinkedIn=reach, HN=views,
    never upvotes), the platform base rate, the per-feature contribution
    ($why), and the lever switches that most raise the win probability."""
    return scorer.score(_client(), platform, features or {}).derived


@mcp.tool()
def experiment_board() -> dict:
    """The Build-Measure-Learn board: the validated-learning rate, the status
    mix, the running bets, and — from Aito — which kinds of experiment tend to
    pay off (P(validated) by effort; small/cheap bets should validate more).
    Honest-weak with few decided experiments."""
    return experiments.board(_client()).derived


@mcp.tool()
def add_experiment(area: str, type: str, hypothesis: str, metric: str,
                   baseline: float, target: float, effort: str) -> dict:
    """Start an experiment (the Build step; status=running). area is an AARRR
    stage (acquisition/activation/revenue/retention/referral); type is
    landing_page/pricing/onboarding/outreach/content/feature; effort is
    small/medium/large; target is the metric value that would validate it."""
    return logbook.add_experiment(
        _client(), area=area, type=type, hypothesis=hypothesis, metric=metric,
        baseline=baseline, target=target, effort=effort)


@mcp.tool()
def log_experiment_result(experiment_id: str, status: str, result: float,
                          learning: str | None = None) -> dict:
    """Resolve a running experiment (the Learn step): record the measured
    result + the verdict (validated/invalidated/inconclusive) + the learning.
    Re-derives `validated` and re-ranks the board."""
    return logbook.log_experiment_result(
        _client(), experiment_id=experiment_id, status=status, result=result,
        learning=learning)


@mcp.tool()
def decision_scorecard() -> dict:
    """The dogfood loop: how often the operator accepts the agent's
    recommendations (overall and by decision_type), and — the key question —
    whether the agent's confidence is trustworthy (Aito's P(accepted) by
    confidence bucket; it should climb low→high). Thin real data means weak,
    honest early numbers."""
    return decisions.scorecard(_client()).derived


@mcp.tool()
def predict(table: str, where: dict, predict_field: str) -> dict:
    """Generic escape hatch: ask Aito for the distribution of any field
    given any conditions, e.g. predict('touches', {'window': '0800'},
    'outcome'). Use linked fields like 'contact_id.segment' in where."""
    return _client().predict(
        {"from": table, "where": where, "predict": predict_field, "limit": 10}
    )


@mcp.prompt()
def populate() -> str:
    """How to populate the pipeline by talking to the agent."""
    return (
        "You are populating a one-person company's sales pipeline in Aito by "
        "turning what the operator tells you into tool calls. Rules:\n\n"
        "1. Every write goes to the live Aito instance, never to the repo's "
        "seed CSVs. Real names, companies, and numbers are fine here — they "
        "live in Aito, not in version control.\n"
        "2. Create the record, then log activity against it:\n"
        "   - a new person  -> add_contact (segment, tier A/B/C, ai_lifecycle, "
        "source, phone_present/email_present as booleans)\n"
        "   - a new opportunity -> add_deal (stage, value_eur, the operator's "
        "own probability 0-100, champion_present, blocker)\n"
        "   - an action to track -> add_todo (area routes it to a view, "
        "operations is the catch-all; action_type + a stakeholder contact and/"
        "or a deal; sales/distribution need a due_date); edit one -> update_todo\n"
        "   - a shipped post -> add_post (channel, tone, reach_or_views, "
        "outcome); a website session -> log_session\n"
        "   - a call/email/meeting that happened -> log_touch\n"
        "   - a deal moved (stage/probability/blocker) -> log_deal_update; a "
        "todo finished -> complete_todo (advances its linked deal)\n"
        "   - a Build-Measure-Learn bet -> add_experiment (running); when it "
        "resolves -> log_experiment_result (the verdict + the learning)\n"
        "   - the operator overrode the agent's suggestion -> log_decision\n"
        "3. Don't invent fields. If the operator hasn't said a contact's tier "
        "or a deal's blocker, ask — or use the honest default (blocker=none). "
        "Validation is strict: an unknown enum value will be rejected loudly, "
        "which is the system working, not a failure to paper over.\n"
        "4. After adding, you can immediately read it back: who_to_call, "
        "deal_pipeline, segment_360, funnel. Early predictions on thin data "
        "are weak and shown weak — that is honest, not broken.\n"
        "5. Phone numbers and email addresses are never stored — only the "
        "phone_present / email_present booleans."
    )


def main() -> None:
    # echo the target instance to stderr (never stdout — that's the MCP
    # stdio channel) so the agent's db is legible, not silent (findings 03).
    import sys
    from .config import Config, instance_host
    try:
        print(f"aito-company-ai MCP → {instance_host(Config.from_env().instance_url)}",
              file=sys.stderr)
    except Exception as exc:  # never block startup on config echo
        print(f"aito-company-ai MCP: config not loaded ({exc})", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
