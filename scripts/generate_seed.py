"""Deterministic synthetic seed generator.

Writes data/seed/ (~50 contacts, 150 touches) and data/seed_tiny/
(10 contacts, 15 touches). Rerunning always produces byte-identical
files; the privacy booktest relies on that to prove the seed CSVs
contain nothing but this generator's output.

THE SYNTHETIC NAMESPACE (docs/06-privacy.md)
Every entity is assembled from the word lists below and is deliberately,
unmistakably fake — placeholder names, not plausible real ones:
- Companies are stock fictional names ("Acme", "Globex") plus a legal
  suffix matched to the contact's country, e.g. "Acme Oy".
- People are placeholder first names with generic surnames, e.g.
  "Bob Stone", "Alice Rivers".
- No phone numbers or email addresses exist anywhere, only
  phone_present / email_present booleans.

THE PLANTED SIGNAL
Outcomes are sampled from a model with deliberate correlations, so that
Aito has something honest to find and booktest snapshots have something
to show: accounting answers in the 0800 window, erp and analytics in
the late window, tier A and warm/referral sources convert better,
contacts with AI already in operation engage more. Cold outreach to
tier C mostly goes unanswered. The same model generates both datasets;
seed_tiny is small enough that the signal is barely visible, which is
the point of keeping it (cold-start honesty).
"""

import csv
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

AS_OF = date(2026, 6, 12)  # fixed so output never depends on the run date
REPO_ROOT = Path(__file__).resolve().parents[1]

# placeholder people: a stock first name + a generic surname. 24×20 combos.
FIRST_NAMES = [
    "Bob", "Alice", "Carol", "Dave", "Eve", "Frank", "Grace", "Heidi",
    "Ivan", "Judy", "Mallory", "Niaj", "Olivia", "Peggy", "Rupert", "Sybil",
    "Trent", "Victor", "Walter", "Yvonne", "Zara", "Quinn", "Mona", "Hank",
]
SURNAMES = [
    "Stone", "Rivers", "Banks", "Fields", "Hill", "Lake", "Brooks", "Frost",
    "Vale", "Marsh", "Reed", "Cross", "Day", "Knight", "Wells", "Pike",
    "Lane", "Ford", "Snow", "Gray",
]
# stock fictional companies — single distinctive tokens, so a mention scan
# can match one cleanly. 60 names; the main seed samples 50.
MOCK_COMPANIES = [
    "Acme", "Globex", "Initech", "Umbrella", "Hooli", "Stark", "Wayne",
    "Wonka", "Cyberdyne", "Soylent", "Vandelay", "Tyrell", "Aperture",
    "Oscorp", "Nakatomi", "Weyland", "Yoyodyne", "Encom", "Abstergo",
    "Gringotts", "Duff", "Bluth", "Sterling", "Dunder", "Pendant",
    "Prestige", "Monarch", "Vehement", "Pied", "Raviga", "Initrode",
    "Mooby", "Sirius", "Spectre", "Virtucon", "Rekall", "Omni", "Tessier",
    "Delos", "Genco", "Sabre", "Lumon", "Zorin", "Krusty", "Strickland",
    "Lacuna", "Pearson", "Hardman", "Gekko", "Vance", "Pierce", "Hanso",
    "Widmore", "Slate", "Atlas", "Vertex", "Nimbus", "Onyx", "Cobalt", "Pymt",
]
SUFFIX_BY_COUNTRY = {
    "Finland": "Oy", "Sweden": "Ab", "Estonia": "OÜ",
    "Germany": "GmbH", "Netherlands": "BV",
}
COUNTRIES = ["Finland"] * 6 + ["Sweden", "Estonia", "Finland", "Germany", "Netherlands"]
ROLES = [
    "CFO", "CEO", "Founder", "Controller", "Head of Finance", "COO",
    "IT Manager", "Head of Product", "CTO", "Finance Manager", "Partner",
]
SEGMENTS = ["accounting"] * 3 + ["erp"] * 2 + ["ecommerce"] * 2 + [
    "analytics", "consultancy", "other",
]
TAG_POOL = [
    "founder-led", "q3-budget", "met-at-event", "newsletter", "inbound",
    "intro-available", "slow-cycle", "tech-savvy", "spreadsheet-heavy",
    "rfp-soon", "podcast-listener", "multi-entity",
]

# planted signal: base p(positive outcome) by (segment, window)
BASE_P = {
    ("accounting", "0800"): 0.55, ("accounting", "1215"): 0.30, ("accounting", "1600"): 0.25,
    ("erp", "0800"): 0.20, ("erp", "1215"): 0.30, ("erp", "1600"): 0.50,
    ("ecommerce", "0800"): 0.25, ("ecommerce", "1215"): 0.45, ("ecommerce", "1600"): 0.35,
    ("analytics", "0800"): 0.25, ("analytics", "1215"): 0.30, ("analytics", "1600"): 0.50,
    ("consultancy", "0800"): 0.45, ("consultancy", "1215"): 0.35, ("consultancy", "1600"): 0.30,
    ("other", "0800"): 0.30, ("other", "1215"): 0.30, ("other", "1600"): 0.30,
}
TIER_ADJ = {"A": 0.15, "B": 0.0, "C": -0.15}
LIFECYCLE_ADJ = {"none": -0.10, "announced": 0.0, "shipped": 0.05, "operating": 0.15}
SOURCE_ADJ = {"warm": 0.15, "referral": 0.20, "trigger": 0.05, "cold": -0.15}

NOTES = {
    "conversation": ["good chat, asked about pricing", "walked through the idea, wants material",
                     "long call, budget talk in autumn", "interested but needs the board"],
    "meeting_booked": ["demo booked", "agreed to a 30min walkthrough"],
    "callback_requested": ["asked to call next week", "in a meeting, call after 15th"],
    "declined": ["no budget this year", "happy with current setup"],
    "reply": ["replied, lukewarm but open", "asked for a one-pager"],
    "bounced": ["address invalid"],
    "no_answer": [""], "no_reply": [""],
}
NEXT_ACTIONS = {
    "conversation": "send pricing summary", "meeting_booked": "prepare demo",
    "callback_requested": "call back", "reply": "send one-pager",
}


def p_positive(contact: dict, window: str) -> float:
    p = (BASE_P[(contact["segment"], window if window != "other" else "1215")]
         + TIER_ADJ[contact["tier"]]
         + LIFECYCLE_ADJ[contact["ai_lifecycle"]]
         + SOURCE_ADJ[contact["source"]])
    return min(0.85, max(0.05, p))


def make_contacts(rng: random.Random, n: int, prefix: str) -> list[dict]:
    contacts = []
    names = rng.sample(
        [(f, s) for f in FIRST_NAMES for s in SURNAMES], n
    )
    companies = rng.sample(MOCK_COMPANIES, n)
    for i in range(n):
        country = rng.choice(COUNTRIES)
        first, last = names[i]
        base = companies[i]
        created = AS_OF - timedelta(days=rng.randint(30, 400))
        contacts.append({
            "contact_id": f"{prefix}{i + 1:03d}",
            "name": f"{first} {last}",
            "company": f"{base} {SUFFIX_BY_COUNTRY[country]}",
            "role": rng.choice(ROLES),
            "phone_present": "true" if rng.random() < 0.8 else "false",
            "email_present": "true" if rng.random() < 0.9 else "false",
            "segment": rng.choice(SEGMENTS),
            "tier": rng.choice(["A", "B", "B", "C", "C"]),
            "ai_lifecycle": rng.choice(["none", "none", "announced", "shipped", "operating"]),
            "source": rng.choice(["warm", "warm", "trigger", "cold", "cold", "referral"]),
            "country": country,
            "notes_tags": ";".join(sorted(rng.sample(TAG_POOL, rng.randint(0, 3)))),
            "created": created.isoformat(),
        })
    return contacts


def business_day(rng: random.Random, days_back_max: int) -> date:
    while True:
        d = AS_OF - timedelta(days=rng.randint(1, days_back_max))
        if d.weekday() < 5:
            return d


WINDOW_TIMES = {"0800": (8, 0, 90), "1215": (12, 15, 45), "1600": (16, 0, 90)}


def make_touches(rng: random.Random, contacts: list[dict], n: int, prefix: str) -> list[dict]:
    weekdays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    # tier A contacts get touched more; some contacts are never touched
    weights = [{"A": 5, "B": 3, "C": 1}[c["tier"]] for c in contacts]
    touched = rng.choices(contacts, weights=weights, k=n)
    touches = []
    for i, contact in enumerate(touched):
        callable_ = contact["phone_present"] == "true"
        emailable = contact["email_present"] == "true"
        channel = rng.choice(
            (["call"] * 3 if callable_ else [])
            + (["email"] * 2 if emailable else [])
            + ["linkedin"]
        )
        if channel in ("call", "meeting"):
            window = rng.choice(["0800", "1215", "1600"])
        else:
            window = rng.choice(["other", "other", "0800", "1215", "1600"])
        # a few of the latest touches land on yesterday so "what changed" has content
        day = AS_OF - timedelta(days=1) if i >= n - 4 else business_day(rng, 70)
        if window == "other":
            hour, minute = rng.choice([(10, 30), (14, 0), (18, 45)])
        else:
            h, m, spread = WINDOW_TIMES[window]
            offset = rng.randint(0, spread)
            hour, minute = h + (m + offset) // 60, (m + offset) % 60
        ts = datetime.combine(day, time(hour, minute))

        positive = rng.random() < p_positive(contact, window)
        if channel in ("call", "meeting"):
            outcome = (rng.choice(["conversation", "conversation", "callback_requested",
                                   "meeting_booked"]) if positive
                       else rng.choice(["no_answer"] * 4 + ["declined"]))
        else:
            outcome = ("reply" if positive
                       else rng.choice(["no_reply"] * 8 + ["bounced", "no_reply"]))

        next_action = NEXT_ACTIONS.get(outcome, "")
        due = ""
        if next_action and rng.random() < 0.8:
            due = (day + timedelta(days=rng.randint(1, 4))).isoformat()
        else:
            next_action = ""
        touches.append({
            "touch_id": f"{prefix}{i + 1:03d}",
            "contact_id": contact["contact_id"],
            "ts": ts.isoformat(),
            "weekday": weekdays[day.weekday()],
            "window": window,
            "channel": channel,
            "outcome": outcome,
            "next_action": next_action,
            "next_action_due": due,
            "notes": rng.choice(NOTES[outcome]),
        })
    touches.sort(key=lambda t: (t["ts"], t["touch_id"]))
    return touches


# ---- website / acquisition funnel (sessions) ----
#
# Planted marketing signal, so Aito has something honest to find in the
# funnel and the dashboard has a story: referral and organic traffic
# convert far better than paid_search and social; mobile signs up fine but
# drops at trial (the planted "mobile trial UX is weak" leak); the
# /pricing and /demo landing pages outperform /blog; one campaign
# ("spring_launch") lifts its sessions, another ("retargeting") barely
# moves them. seed_tiny is too small to show the signal cleanly — that is
# the cold-start honesty gate, same as the rest of the data.

WEB_SOURCES = ["organic", "organic", "paid_search", "paid_search", "social",
               "referral", "direct"]
DEVICES = ["desktop", "desktop", "mobile", "mobile", "tablet"]
LANDING_PAGES = ["/", "/pricing", "/docs", "/blog", "/demo"]
CAMPAIGNS = {
    "paid_search": ["spring_launch", "retargeting", "brand_terms"],
    "social": ["spring_launch", "retargeting", "founder_thread"],
    "organic": [""], "referral": [""], "direct": [""],
}

# base p(signup) by source, then trial|signup and paid|trial conditionals
SIGNUP_P = {"organic": 0.34, "paid_search": 0.22, "social": 0.18,
            "referral": 0.45, "direct": 0.30}
SOURCE_TRIAL_ADJ = {"organic": 0.05, "paid_search": -0.05, "social": -0.08,
                    "referral": 0.12, "direct": 0.0}
LANDING_SIGNUP_ADJ = {"/": -0.05, "/pricing": 0.12, "/docs": 0.0,
                      "/blog": -0.10, "/demo": 0.15}
CAMPAIGN_ADJ = {"spring_launch": 0.10, "retargeting": 0.01,
                "brand_terms": 0.06, "founder_thread": 0.08, "": 0.0}


def make_sessions(rng: random.Random, n: int, prefix: str) -> list[dict]:
    sessions = []
    for i in range(n):
        source = rng.choice(WEB_SOURCES)
        device = rng.choice(DEVICES)
        landing = rng.choice(LANDING_PAGES)
        campaign = rng.choice(CAMPAIGNS[source])
        day = AS_OF - timedelta(days=rng.randint(1, 120))

        p_signup = min(0.9, max(0.03,
            SIGNUP_P[source] + LANDING_SIGNUP_ADJ[landing] + CAMPAIGN_ADJ[campaign]))
        signed_up = rng.random() < p_signup

        # trial conditional on signup; mobile drops here (planted leak)
        p_trial = 0.55 + SOURCE_TRIAL_ADJ[source] - (0.25 if device == "mobile" else 0.0)
        started_trial = signed_up and rng.random() < max(0.05, p_trial)

        # paid conditional on trial; referral/organic close better
        p_paid = 0.40 + SOURCE_TRIAL_ADJ[source]
        converted_paid = started_trial and rng.random() < max(0.05, p_paid)

        sessions.append({
            "session_id": f"{prefix}{i + 1:04d}",
            "ts": day.isoformat(),
            "source": source,
            "campaign": campaign,
            "landing_page": landing,
            "country": rng.choice(COUNTRIES),
            "device": device,
            "signed_up": "true" if signed_up else "false",
            "started_trial": "true" if started_trial else "false",
            "converted_paid": "true" if converted_paid else "false",
        })
    sessions.sort(key=lambda s: (s["ts"], s["session_id"]))
    return sessions


# ---- distribution / messaging formula (posts) ----
#
# Planted doctrine (operator-ground-truth.md §3), so the scorer learns the
# real levers: narrate >> announce; a LinkedIn link in the body craters
# reach ~10x vs first comment; HN is binary (front page or ~8-30 views);
# AI-voice gets flagged and buried on general channels (HN, big reddit) but
# is tolerated on niche/explainer drops. `won` is derived per channel from
# reach_or_views (LI reach / HN views), NEVER from upvotes — upvotes is
# logged but noisy so the "quiet win" (high views, low upvotes) survives.

POST_CHANNELS = ["linkedin", "linkedin", "linkedin", "hackernews", "reddit", "blog"]
TONES = ["narrate", "announce", "explainer", "builder"]
AI_MADES = ["manual", "manual", "ai-assisted", "ai"]
POST_FORMATS_BY_CHANNEL = {
    "linkedin": ["text", "link"],
    "hackernews": ["show-hn", "link"],
    "reddit": ["link", "text"],
    "blog": ["link", "demo-link"],
}
POST_TOPICS = ["agent_inference", "positioning", "product", "customer_proof",
               "oss_tool", "core_product"]
CHANNEL_BASE = {"linkedin": 320, "hackernews": 28, "reddit": 420, "blog": 150}
TONE_MULT = {"narrate": 2.2, "announce": 0.6, "explainer": 1.2, "builder": 1.4}
# per-channel win threshold on reach_or_views (LI=reach, HN=views, ...)
WIN_AT = {"linkedin": 600, "hackernews": 700, "reddit": 820, "blog": 300}
MODEST_AT = {"linkedin": 200, "hackernews": 50, "reddit": 250, "blog": 90}


def _post_reach(rng: random.Random, channel: str, tone: str, ai_made: str,
                fmt: str, link_placement: str, length_chars: int, weekday: str) -> int:
    reach = CHANNEL_BASE[channel] * TONE_MULT[tone]
    if channel == "linkedin" and link_placement == "body":
        reach *= 0.12                                   # the link-in-body crater
    if channel in ("hackernews", "reddit"):
        reach *= {"manual": 1.0, "ai-assisted": 0.8, "ai": 0.3}[ai_made]  # flagged
    else:
        reach *= {"manual": 1.0, "ai-assisted": 0.95, "ai": 0.7}[ai_made]
    reach *= 0.9 if length_chars > 450 else 1.05 if length_chars > 250 else 1.0
    if channel == "linkedin":
        reach *= 1.15 if weekday in ("tue", "wed", "fri") else 0.9
    # HN is binary: a hero drop (manual builder/narrate show-hn) can hit the front page
    if channel == "hackernews":
        hero = fmt == "show-hn" and ai_made == "manual" and tone in ("narrate", "builder")
        if hero and rng.random() < 0.30:
            reach *= 40
    reach *= rng.uniform(0.7, 1.4)                       # noise
    return max(3, int(reach))


MATERIAL_TYPE_POOL = ["blog", "blog", "demo", "whitepaper", "thread", "note", "video", "talk"]
MATERIAL_SHAPE = ["notes", "deep dive", "teardown", "story", "guide", "benchmark"]
# the channel catalog: r/programming and r/Python both roll up to reddit.
CHANNEL_CATALOG = [
    ("Hacker News", "hackernews"), ("r/programming", "reddit"),
    ("r/Python", "reddit"), ("LinkedIn", "linkedin"), ("Company blog", "blog"),
]


def make_channels(prefix: str) -> list[dict]:
    created = (AS_OF - timedelta(days=400)).isoformat()
    return [{"channel_id": f"{prefix}{i + 1:02d}", "name": name,
             "platform": platform, "created": created}
            for i, (name, platform) in enumerate(CHANNEL_CATALOG)]


def make_materials(rng: random.Random, n: int, prefix: str) -> list[dict]:
    rows = []
    for i in range(n):
        topic = rng.choice(POST_TOPICS)
        rows.append({
            "material_id": f"{prefix}{i + 1:03d}",
            "type": rng.choice(MATERIAL_TYPE_POOL),
            "title": f"{topic.replace('_', ' ')} {rng.choice(MATERIAL_SHAPE)}",
            "topic": topic,
            "lane": rng.choice(["warm", "warm", "cold"]),
            "ai_made": rng.choice(AI_MADES),
            "length_chars": rng.choice([120, 180, 240, 320, 420, 540, 680]),
            "created": (AS_OF - timedelta(days=rng.randint(1, 200))).isoformat(),
        })
    return rows


def make_posts(rng: random.Random, materials: list[dict], channels: list[dict],
               n: int, prefix: str) -> list[dict]:
    weekdays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    posts = []
    for i in range(n):
        material = rng.choice(materials)
        channel = rng.choice(channels)
        platform = channel["platform"]
        tone = rng.choice(TONES)
        fmt = rng.choice(POST_FORMATS_BY_CHANNEL[platform])
        link_placement = rng.choice(["comment", "comment", "body"]) if platform == "linkedin" else "n_a"
        row = {
            "post_id": f"{prefix}{i + 1:04d}", "material_id": material["material_id"],
            "channel_id": channel["channel_id"], "status": "posted",
            "posted_at": "", "tone": tone, "format": fmt, "link_placement": link_placement,
            "reach_or_views": "", "upvotes": "", "trials": "", "outcome": "",
        }
        # ~75% are posted (with KPIs); the rest sit in the go/no-go lifecycle
        if rng.random() < 0.75:
            day = business_day(rng, 120) if platform == "linkedin" else \
                AS_OF - timedelta(days=rng.randint(1, 120))
            wd = weekdays[day.weekday()]
            reach = _post_reach(rng, platform, tone, material["ai_made"], fmt,
                                link_placement, material["length_chars"], wd)
            outcome = ("win" if reach >= WIN_AT[platform]
                       else "modest" if reach >= MODEST_AT[platform] else "flop")
            upvotes = max(0, int(reach / rng.uniform(35, 90)))
            if platform == "hackernews" and rng.random() < 0.4:
                upvotes = int(upvotes * 0.3)
            trials = (max(0, int(reach / 800 * rng.uniform(0.5, 2.0)))
                      if material["lane"] == "cold" else 0)
            row.update({"posted_at": day.isoformat(), "reach_or_views": reach,
                        "upvotes": upvotes, "trials": trials, "outcome": outcome})
        else:
            row["status"] = rng.choice(["planned", "planned", "go", "no_go"])
        posts.append(row)
    posts.sort(key=lambda p: (p["posted_at"] or "9999", p["post_id"]))
    return posts


# ---- todos (the action source) ----
#
# Synthetic actions across the four areas. Sales/distribution are
# time-driven (due_date + window, clustered near AS_OF so the Now view and
# the calendar lens have live content); operations/R&D are priority-driven
# (no due_date, ranked). Sales todos link to seed contacts so the action
# surface ties back to the rolodex. No PII: titles use the synthetic
# company namespace and generic action verbs.

TODO_WINDOWS = ["mon_0800", "tue_0800", "wed_am", "fri_1430", "fri_1530", "fri_eve"]
SALES_ACTIONS = ["Call {co} before the window closes", "Reference ask with {co}",
                 "Reposition email to {co}", "Follow-up call with {co}",
                 "Send pricing context to {co}"]
DIST_ACTIONS = ["Ship the {topic} post", "Draft the {topic} narrative",
                "Repurpose {topic} for LinkedIn", "Propagate the {topic} demo"]
DIST_TOPICS = ["agent-inference", "positioning", "oss-tool", "customer-proof", "product"]
OPS_ITEMS = ["{co} instance isolation check", "{co} license renewal window",
             "{co} usage anomaly review", "{co} uptime report"]
RND_ITEMS = ["Rep2 stabilization", "pg_infer extension", "Booktest end-to-end verify",
             "Predictive-DB benchmark", "Schema migration tooling"]
EXP_ACTIONS = ["Analyze the {topic} test results", "Set up the {topic} experiment",
               "Review the {topic} cohort", "Decide go/kill on {topic}"]
PREP = ["prep_needed", "ready", "in_progress"]

# the action verb, inferred from the title's lead word, else an area default —
# so Pass 2's Aito classifier has a real title→action_type signal to learn.
_AREA_ACTION = {"sales": "call", "marketing": "post", "operations": "admin",
                "rnd": "research", "experiments": "research"}
SLOTS = ["09:00", "10:30", "13:00", "14:30", "15:30", "16:00"]


def _infer_action(title, area):
    t = title.lower()
    if t.startswith("call"):
        return "call"
    if t.startswith(("reference ask", "reposition", "send", "email", "follow-up")):
        return "email"
    if t.startswith(("meet", "book", "demo")):
        return "meeting"
    if t.startswith(("ship", "post", "draft", "repurpose", "propagate", "publish")):
        return "post"
    if t.startswith(("analyze", "review", "investigate", "decide", "set up")):
        return "research"
    return _AREA_ACTION.get(area, "none")


# planted slip signal for closed-todo history: P(slipped) by feature. The
# scorer recovers it — prep-needed and blocked work slips, low priority
# slips, ready high-priority rarely does. (operator intuition, synthetic.)
SLIP_PREP = {"prep_needed": 0.55, "ready": 0.10, "in_progress": 0.30,
             "blocked": 0.75, "n_a": 0.25}
SLIP_PRIORITY = {1: -0.10, 2: 0.0, 3: 0.15}


def make_todo_history(rng, contacts, n, prefix):
    """Closed (done) todos carrying the slipped outcome — the training
    substrate for slip-risk. Excluded from the lenses (status=done)."""
    companies = [c["company"] for c in contacts]
    areas = ["sales", "marketing", "operations", "rnd"]
    rows = []
    for i in range(n):
        area = rng.choice(areas)
        prep = rng.choice(["prep_needed", "ready", "in_progress", "blocked", "n_a"])
        priority = rng.choices([1, 2, 3], weights=[3, 4, 3])[0]
        p_slip = min(0.92, max(0.04, SLIP_PREP[prep] + SLIP_PRIORITY[priority]))
        slipped = rng.random() < p_slip
        co = rng.choice(companies)
        title = (rng.choice(SALES_ACTIONS).format(co=co) if area == "sales"
                 else rng.choice(DIST_ACTIONS).format(topic=rng.choice(DIST_TOPICS)) if area == "marketing"
                 else rng.choice(OPS_ITEMS).format(co=co) if area == "operations"
                 else rng.choice(RND_ITEMS))
        rows.append({
            "todo_id": f"{prefix}h{i + 1:03d}", "area": area, "title": title,
            "detail": "", "action_type": _infer_action(title, area),
            "status": "done", "priority": priority,
            "due_date": "", "window": "", "slot": "", "linked_id": "", "linked_type": "",
            "stakeholder_id": "", "prep_status": prep,
            "slipped": "true" if slipped else "false",
        })
    return rows


def make_todos(rng, contacts, deals, n, prefix):
    todos = []
    companies = [c["company"] for c in contacts]
    by_company = {}
    for c in contacts:
        by_company.setdefault(c["company"], []).append(c["contact_id"])
    # sales todos link to OPEN deals — the action advances that opportunity,
    # so completing it can move the deal (the closed loop, docs/13).
    open_deals = [d for d in deals
                  if d["stage"] not in ("closed_won", "closed_lost", "parked")]

    def base(tid, area, title):
        # role/owner are the agent-lane routing columns (docs/12); the generator
        # leaves them empty (seed work is unrouted), but they must be present so
        # the seed CSV matches the schema and the committed data byte-for-byte.
        return {"todo_id": tid, "area": area, "title": title, "detail": "",
                "action_type": _infer_action(title, area), "slot": "",
                "linked_id": "", "linked_type": "", "stakeholder_id": "",
                "role": "", "owner": ""}

    for i in range(n):
        area = rng.choices(["sales", "marketing", "operations", "rnd", "experiments"],
                           weights=[4, 3, 2, 3, 2])[0]
        tid = f"{prefix}{i + 1:03d}"
        if area == "sales":
            deal = rng.choice(open_deals)
            day = AS_OF + timedelta(days=rng.randint(-2, 6))
            while day.weekday() >= 5:
                day += timedelta(days=1)
            row = base(tid, area, rng.choice(SALES_ACTIONS).format(co=deal["company"]))
            # the stakeholder: a contact at the deal's company, when we have one
            stake = by_company.get(deal["company"])
            row.update({
                "status": rng.choice(["ready", "draft", "prog"]),
                "priority": rng.choices([1, 2, 3], weights=[3, 4, 3])[0],
                "due_date": day.isoformat(), "window": rng.choice(TODO_WINDOWS),
                "slot": rng.choice(SLOTS),
                "linked_id": deal["deal_id"], "linked_type": "deal",
                "stakeholder_id": rng.choice(stake) if stake else "",
                "prep_status": rng.choice(PREP),
            })
            todos.append(row)
        elif area == "marketing":
            day = AS_OF + timedelta(days=rng.randint(-1, 8))
            while day.weekday() >= 5:
                day += timedelta(days=1)
            row = base(tid, area, rng.choice(DIST_ACTIONS).format(topic=rng.choice(DIST_TOPICS)))
            row.update({
                "status": rng.choice(["ready", "draft", "prog"]),
                "priority": rng.choices([1, 2, 3], weights=[2, 4, 4])[0],
                "due_date": day.isoformat(), "window": rng.choice(TODO_WINDOWS),
                "slot": rng.choice(SLOTS),
                "linked_type": "asset", "prep_status": rng.choice(PREP),
            })
            todos.append(row)
        elif area == "operations":
            row = base(tid, area, rng.choice(OPS_ITEMS).format(co=rng.choice(companies)))
            # ~40% of ops work has a deadline (renewals, reports) → a due date +
            # slot; the rest is ongoing (priority only). due is optional here.
            has_deadline = rng.random() < 0.4
            day = AS_OF + timedelta(days=rng.randint(-1, 10))
            while has_deadline and day.weekday() >= 5:
                day += timedelta(days=1)
            row.update({
                "status": rng.choice(["monitor", "on_track", "blocked"]),
                "priority": rng.choices([1, 2, 3], weights=[2, 4, 4])[0],
                "due_date": day.isoformat() if has_deadline else "",
                "window": "", "slot": rng.choice(SLOTS) if has_deadline else "",
                "linked_type": "instance", "prep_status": "n_a",
            })
            todos.append(row)
        elif area == "experiments":
            row = base(tid, area, rng.choice(EXP_ACTIONS).format(topic=rng.choice(DIST_TOPICS)))
            row.update({
                "status": rng.choice(["ready", "prog", "blocked"]),
                "priority": rng.choices([1, 2, 3], weights=[3, 4, 3])[0],
                "due_date": "", "window": "",
                "linked_type": "workstream", "prep_status": rng.choice(PREP),
            })
            todos.append(row)
        else:  # rnd
            row = base(tid, area, rng.choice(RND_ITEMS))
            row.update({
                "status": rng.choice(["prog", "blocked", "ready"]),
                "priority": rng.choices([1, 2, 3], weights=[3, 3, 4])[0],
                "due_date": "", "window": "",
                "linked_type": "workstream", "prep_status": rng.choice(PREP),
            })
            todos.append(row)
    for t in todos:
        t["slipped"] = ""  # open todos have no outcome yet
    todos.sort(key=lambda t: (t["area"], t["priority"], t["todo_id"]))
    return todos


# ---- deals (the sales pipeline) ----
#
# Open deals are the current pipeline; closed deals carry the win/loss the
# risk predictor learns from. Planted signal: a present champion and warm
# momentum win; a blocker, no champion, and a long touch gap lose. The
# predictor recovers "which open deals are at risk, and why".
DEAL_BLOCKERS = ["none", "none", "consultant_lock", "timing_mismatch",
                 "demo_readiness", "budget", "no_champion"]
DEAL_OPEN_STAGES = ["lead", "qualified", "demo", "pilot", "negotiation"]


def _deal_won_p(champion, blocker, probability, days_since):
    p = 0.30
    p += 0.25 if champion else -0.15
    p += -0.20 if blocker != "none" else 0.10
    p += (probability - 50) / 200.0          # the operator's own estimate carries signal
    p += -0.15 if days_since > 30 else 0.0   # stalled deals lose
    return min(0.92, max(0.05, p))


def make_deals(rng, companies, n_open, n_closed, prefix):
    segs = ["accounting", "erp", "ecommerce", "analytics", "consultancy", "other"]
    rows = []

    # deals are with companies you have contacts at — so a sales todo can link
    # a stakeholder (a contact) at the deal's company. Falls back to a fresh
    # name if the rolodex is empty.
    def company():
        if companies:
            return rng.choice(companies)
        return f"{rng.choice(COMPANY_HEADS)}{rng.choice(COMPANY_TAILS)} {rng.choice(['Oy', 'Ab'])}"

    # open pipeline
    for i in range(n_open):
        champion = rng.random() < 0.55
        blocker = rng.choice(DEAL_BLOCKERS)
        prob = rng.choice([20, 30, 40, 50, 60, 65, 70])
        last = AS_OF - timedelta(days=rng.randint(1, 45))
        rows.append({
            "deal_id": f"{prefix}{i + 1:03d}", "company": company(),
            "segment": rng.choice(segs), "stage": rng.choice(DEAL_OPEN_STAGES),
            "value_eur": rng.choice([15000, 22500, 35000, 45000, 60000, 80000]),
            "probability": prob, "champion_present": "true" if champion else "false",
            "blocker": blocker, "last_touch_date": last.isoformat(),
            "created": (last - timedelta(days=rng.randint(20, 300))).isoformat(),
        })
    # closed history (won/lost), the training substrate
    for i in range(n_closed):
        champion = rng.random() < 0.5
        blocker = rng.choice(DEAL_BLOCKERS)
        prob = rng.choice([20, 30, 40, 50, 60, 70, 80])
        days = rng.randint(1, 80)
        last = AS_OF - timedelta(days=rng.randint(30, 400))
        won = rng.random() < _deal_won_p(champion, blocker, prob, days)
        rows.append({
            "deal_id": f"{prefix}c{i + 1:03d}", "company": company(),
            "segment": rng.choice(segs),
            "stage": "closed_won" if won else "closed_lost",
            "value_eur": rng.choice([15000, 22500, 35000, 45000, 60000, 80000]),
            "probability": prob, "champion_present": "true" if champion else "false",
            "blocker": blocker, "last_touch_date": last.isoformat(),
            "created": (last - timedelta(days=rng.randint(20, 300))).isoformat(),
        })
    rows.sort(key=lambda d: (d["stage"], d["deal_id"]))
    return rows


# ---- decisions (the dogfood loop: agent recommended -> human did) ----
#
# Planted signal: the operator accepts the agent more when it was confident,
# so the scorecard can ask "is the agent's confidence trustworthy?" — high
# confidence should track high acceptance. followup_timing is accepted most,
# call_priority overridden most (the operator trusts the model on timing,
# less on who-to-call-first), so per-type rates differ too.
DECISION_TYPES = ["call_priority", "opener_choice", "followup_timing"]
TYPE_ACCEPT_ADJ = {"call_priority": -0.15, "opener_choice": 0.0, "followup_timing": 0.15}
DECISION_OUTCOMES = ["", "", "good", "neutral", "missed"]


def make_decisions(rng, contacts, n, prefix):
    weekdays = ["mon", "tue", "wed", "thu", "fri"]
    rows = []
    for i in range(n):
        c = rng.choice(contacts)
        dtype = rng.choice(DECISION_TYPES)
        conf = round(rng.uniform(0.1, 0.95), 2)
        p_accept = min(0.95, max(0.05, 0.15 + conf * 0.7 + TYPE_ACCEPT_ADJ[dtype]))
        if rng.random() < p_accept:
            action, alt = "accepted", ""
        else:
            action = rng.choice(["overridden", "overridden", "ignored"])
            alt = "reordered" if action == "overridden" else ""
        rows.append({
            "decision_id": f"{prefix}{i + 1:03d}",
            "ts": (AS_OF - timedelta(days=rng.randint(1, 90))).isoformat() + "T08:10:00",
            "decision_type": dtype,
            "context_window": rng.choice(["0800", "1215", "1600"]),
            "context_weekday": rng.choice(weekdays),
            "context_segment": c["segment"], "context_tier": c["tier"],
            "context_ai_lifecycle": c["ai_lifecycle"],
            "chosen": c["contact_id"], "agent_confidence": conf,
            "human_action": action, "human_alternative": alt,
            "outcome_after": rng.choice(DECISION_OUTCOMES) if action == "accepted" else "",
        })
    rows.sort(key=lambda d: (d["ts"], d["decision_id"]))
    return rows


# ---- experiments (the Build-Measure-Learn loop) ----
#
# Planted signal: small experiments validate more often than large ones
# (small 0.62 -> large 0.28), so the board recovers the Lean doctrine —
# favour cheap, fast bets. activation tweaks (onboarding) pay off a little
# more than the rest. ~70% reach a verdict; the rest are running/abandoned.
EXPERIMENT_AREAS = ["acquisition", "activation", "revenue", "retention", "referral"]
EXPERIMENT_TYPES = ["landing_page", "pricing", "onboarding", "outreach", "content", "feature"]
AREA_METRIC = {
    "acquisition": "signup_rate", "activation": "trial_start_rate",
    "revenue": "trial_to_paid", "retention": "m1_retention", "referral": "referral_rate",
}
EFFORT_P = {"small": 0.70, "medium": 0.42, "large": 0.18}
AREA_ADJ = {"activation": 0.10, "acquisition": 0.0, "referral": 0.0,
            "revenue": -0.05, "retention": -0.05}


def make_experiments(rng, n, prefix):
    rows = []
    for i in range(n):
        area = rng.choice(EXPERIMENT_AREAS)
        etype = rng.choice(EXPERIMENT_TYPES)
        # small experiments are the common case (Lean: prefer cheap bets)
        effort = rng.choices(["small", "medium", "large"], weights=[5, 3, 2])[0]
        metric = AREA_METRIC[area]
        baseline = round(rng.uniform(0.04, 0.40), 3)
        target = round(baseline * rng.uniform(1.2, 1.8), 3)
        p_val = min(0.92, max(0.05, EFFORT_P[effort] + AREA_ADJ[area]))

        roll = rng.random()
        if roll < 0.17:
            status, result, decided, learning = "running", "", "", ""
        elif roll < 0.25:
            status, result, decided, learning = "abandoned", "", "", "killed before a verdict"
        else:
            if rng.random() < p_val:
                status = "validated"
                result = round(target * rng.uniform(1.0, 1.35), 3)
                learning = f"{metric} reached {result}; shipped"
            elif rng.random() < 0.82:
                status = "invalidated"
                result = round(baseline * rng.uniform(0.85, 1.1), 3)
                learning = "no lift over baseline; reverted"
            else:
                status = "inconclusive"
                result = round(target * rng.uniform(0.92, 1.05), 3)
                learning = "signal within noise; needs a bigger sample"

        started = AS_OF - timedelta(days=rng.randint(5, 150))
        decided = (started + timedelta(days=rng.randint(5, 35))).isoformat() \
            if status in ("validated", "invalidated", "inconclusive") else ""
        rows.append({
            "experiment_id": f"{prefix}{i + 1:03d}",
            "created": started.isoformat(), "area": area, "type": etype,
            "hypothesis": f"A {etype} change lifts {metric} from {baseline} to {target}.",
            "metric": metric, "baseline": baseline, "target": target,
            "result": result, "effort": effort, "status": status,
            "learning": learning, "started": started.isoformat(), "decided": decided,
        })
    rows.sort(key=lambda e: (e["started"], e["experiment_id"]))
    return rows


# ---- events to attend (the go/no-go lifecycle) ----
EVENT_NAMES = ["PyData", "ProductCon", "SaaStr Europe", "DevMeetup", "AI Summit",
               "Founders Brunch", "Indie Hackers", "Postgres Conf", "ML Connect"]
EVENT_TYPE_POOL = ["conference", "conference", "meetup", "webinar", "talk", "sponsor"]
EVENT_CITIES = ["Helsinki", "Berlin", "Amsterdam", "Stockholm", "online", "online"]


def make_events(rng, n, prefix):
    rows = []
    for i in range(n):
        starts = AS_OF + timedelta(days=rng.randint(-60, 120))
        loc = rng.choice(EVENT_CITIES)
        cost = 0 if loc == "online" else rng.choice([0, 150, 300, 600, 1200])
        decided, outcome, notes = "", "", ""
        roll = rng.random()
        if roll < 0.35:
            status = "candidate"
        elif roll < 0.55:
            status, notes = "no_go", "low fit for the cost"
        elif roll < 0.80:
            status, notes = "go", "worth a talk / booth"
        else:
            status = "attended"
            outcome = rng.choice(["worthwhile", "worthwhile", "neutral", "waste"])
            notes = "post-event notes"
        if status != "candidate":
            decided = (starts - timedelta(days=rng.randint(5, 30))).isoformat()
        rows.append({
            "event_id": f"{prefix}{i + 1:03d}",
            "name": f"{rng.choice(EVENT_NAMES)} 2026",
            "type": rng.choice(EVENT_TYPE_POOL),
            "starts": starts.isoformat(), "location": loc, "cost_eur": str(cost),
            "status": status, "decided": decided, "outcome": outcome, "notes": notes,
            "created": (AS_OF - timedelta(days=rng.randint(10, 120))).isoformat(),
        })
    rows.sort(key=lambda e: (e["starts"], e["event_id"]))
    return rows


# ---- routines (recurring agentic tasks) ----
# a fixed standing list (these are the operator's real routines, not random)
ROUTINE_SPECS = [
    ("Monday outreach prep", "sales", "weekly", "mon", "", "prospects", "next outbound batch"),
    ("Prepare the week", "operations", "weekly", "sun", "", "brief", ""),
    ("Friday board review", "operations", "weekly", "fri", "", "brief", ""),
    ("Weekly content batch", "marketing", "weekly", "tue", "", "none", "draft + schedule posts"),
    ("Pipeline hygiene", "sales", "weekly", "wed", "", "none", "update stages, clear stale"),
    ("Monthly bookkeeping", "operations", "monthly", "", "1", "none", ""),
    ("Monthly metrics review", "rnd", "monthly", "", "5", "none", ""),
]


def make_routines(n, prefix):
    created = (AS_OF - timedelta(days=30)).isoformat()
    rows = []
    for i, (title, area, cadence, wd, dom, prep, notes) in enumerate(ROUTINE_SPECS[:n]):
        rows.append({
            "routine_id": f"{prefix}{i + 1:02d}", "title": title, "area": area,
            "cadence": cadence, "weekday": wd, "day_of_month": dom, "prep": prep,
            "prompt": "", "last_done": "", "active": "true", "notes": notes,
            "created": created,
        })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate(out_dir: Path, n_contacts: int, n_touches: int, n_sessions: int,
             n_materials: int, n_posts: int, n_todos: int, n_todo_history: int,
             n_deals_open: int, n_deals_closed: int, n_decisions: int,
             n_experiments: int, n_events: int, n_routines: int,
             seed: int, prefix: str) -> None:
    rng = random.Random(seed)
    contacts = make_contacts(rng, n_contacts, f"{prefix}c")
    touches = make_touches(rng, contacts, n_touches, f"{prefix}t")
    sessions = make_sessions(rng, n_sessions, f"{prefix}s")
    # marketing: materials (content) + channels (destinations) → posts (material×channel)
    channels = make_channels(f"{prefix}k")
    materials = make_materials(rng, n_materials, f"{prefix}m")
    posts = make_posts(rng, materials, channels, n_posts, f"{prefix}p")
    # deals before todos: sales todos link to open deals (the closed loop)
    deals = make_deals(rng, [c["company"] for c in contacts],
                       n_deals_open, n_deals_closed, f"{prefix}e")
    # open worklist + closed history (the slip-risk training substrate)
    todos = make_todos(rng, contacts, deals, n_todos, f"{prefix}d") \
        + make_todo_history(rng, contacts, n_todo_history, f"{prefix}d")
    decisions = make_decisions(rng, contacts, n_decisions, f"{prefix}x")
    experiments = make_experiments(rng, n_experiments, f"{prefix}r")
    events = make_events(rng, n_events, f"{prefix}v")
    routines = make_routines(n_routines, f"{prefix}o")
    write_csv(out_dir / "rolodex.csv", contacts)
    write_csv(out_dir / "touches.csv", touches)
    write_csv(out_dir / "sessions.csv", sessions)
    write_csv(out_dir / "materials.csv", materials)
    write_csv(out_dir / "channels.csv", channels)
    write_csv(out_dir / "posts.csv", posts)
    write_csv(out_dir / "todos.csv", todos)
    write_csv(out_dir / "deals.csv", deals)
    write_csv(out_dir / "decisions.csv", decisions)
    write_csv(out_dir / "experiments.csv", experiments)
    write_csv(out_dir / "events.csv", events)
    write_csv(out_dir / "routines.csv", routines)
    print(f"{out_dir}: {len(contacts)} contacts, {len(touches)} touches, "
          f"{len(sessions)} sessions, {len(materials)} materials, "
          f"{len(channels)} channels, {len(posts)} posts, {len(todos)} todos, "
          f"{len(deals)} deals, {len(decisions)} decisions, "
          f"{len(experiments)} experiments, {len(events)} events, "
          f"{len(routines)} routines")


if __name__ == "__main__":
    generate(REPO_ROOT / "data" / "seed", 50, 150, 600, 40, 120, 22, 80, 15, 65, 60, 90, 14, 7,
             seed=20260612, prefix="s")
    generate(REPO_ROOT / "data" / "seed_tiny", 10, 15, 30, 8, 12, 6, 10, 4, 10, 8, 6, 4, 4,
             seed=11, prefix="y")
