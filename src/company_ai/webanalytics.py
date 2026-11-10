"""aito.ai web analytics: Amplitude page views as web_sessions rows (docs/35).

One UTC day of visits becomes one row per session. A session belongs to the
day of its first event, so a pull reads the day before and after as well and
keeps the sessions that started on the day. The export holds raw user ids,
device ids, IPs and full URLs; none of it is kept. Rows are built field by
field (an allow-list), paths are cut at `?`/`#` and email-shaped or token-like
segments are redacted, utm values are charset-limited, and the session key is
a hash of the session's own ids. The export is parsed in memory and never
written to disk.

Classification here (source from utm_medium/referrer, device class from the
OS, probe paths) is a fixed label lookup, not a score. Every prediction is an
Aito query (rule 2): `predict_next_path`, and `onward_drivers` (_relate).
"""

import fcntl
import gzip
import hashlib
import hmac
import io
import json
import os
import re
import tempfile
import uuid
import zipfile
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urlsplit

import requests

from . import relations, schema
from pathlib import Path

from .aito import AitoClient

EXPORT_URL = "https://analytics.eu.amplitude.com/api/2/export"
SITE_HOST = "aito.ai"
LOOKBACK_DAYS = 3   # referrer_day: a post on the referrer's platform this many days before
# tier 2 (docs/35): how many days after posting a visit from the post's
# platform to its link_path is matched to it. An attribution threshold, so
# Antti's to set: default 7, COMPANY_AI_WEB_MATCH_DAYS overrides it.
MATCH_DAYS = int(os.environ.get("COMPANY_AI_WEB_MATCH_DAYS", "7"))
# tier 3 (inferred) is parked until this many sessions are labelled by tiers
# 1-2 (CPO, 6.11.2026); web_traffic reports the count against it
INFERENCE_TRIGGER = 30

# the two page-view shapes the site sends (docs/35)
PAGE_VIEW_PREFIXES = {"Page View": "Page View: ", "Viewed": "Viewed"}
CTA_SUFFIX = "_cta_clicked"
SIGNUP_PATHS = ("/signup", "/sign-up", "/register")
NO_SESSION = (-1, None)   # Amplitude's "no session": each such event stands alone

# The preselected KPIs (docs/36, chosen by Antti 5.11.2026), from the real
# Amplitude event names seen 6.10-5.11.2026. A session has the KPI when any of
# its events has one of these names. A new name is not guessed into a KPI:
# the pull reports names it has never seen (new_event_types).
KPI_EVENTS = {
    # by its page, not its event name (KPI_PAGES): a demo's pricing estimator
    # and beta's /pricing/ are not aito.ai's pricing page (Antti, 10.11.2026)
    "pricing_page": set(),
    "contact_page": {"Page View: /contact-us/"},
    "login_page": {"Page View: Sign In"},
    "signup": {"Page View: Sign Up", "Page View: /sign-up/", "signup_clicked", "signup_completed"},
    "sandbox": {"sandbox_created", "Instance create", "Instance ready"},
    "data_loaded": {"File upload", "data_uploaded"},
    "first_query": {"Workbook query executed", "playground_query_executed"},
    "api_keys": {"Get API keys"},
}
# KPIs reached by viewing a page, matched by its host and path as `_page`
# writes it: aito.ai's own pages bare ("/pricing/"), other hosts host-first
# ("beta.aito.ai/pricing/"), so another site's page of the same name never
# counts. A session has the KPI when it viewed one of these pages.
KPI_PAGES = {
    "pricing_page": {"/pricing/"},
}
assert set(KPI_PAGES) <= set(KPI_EVENTS)
# Amplitude's own session bookkeeping: not something the visitor did
LIFECYCLE_EVENTS = {"session_start", "session_end"}
# The product events seen in the export 6.10-5.11.2026 that are not KPI
# events. A name outside these and KPI_EVENTS is reported as new_event_types,
# so someone decides whether it belongs to a KPI; it is never guessed in.
KNOWN_EVENT_TYPES = {
    "signin_clicked", "tour_started", "tour_step", "tour_skipped",
    "demo_recommendations_fetched", "demo_autocomplete_fetched", "demo_persona_selected",
    "demo_product_added_to_cart", "demo_search_executed", "demo_price_estimated",
    # the pricing estimator demo: once in the pricing KPI by name, it isn't
    # aito.ai's pricing page (KPI_PAGES)
    "Page View: Demo - Pricing",
    "Instance delete", "Instance delete now",
}
_KPI_EVENT_NAMES = set().union(*KPI_EVENTS.values())

# utm_source values that name a posting platform (docs/35 attribution): an
# exact link needs the visit's platform to be the post's. Anything else
# matches only a tag used on a single platform.
UTM_SOURCE_PLATFORMS = {"linkedin": "linkedin", "linkedin.com": "linkedin", "lnkd.in": "linkedin",
                        "reddit": "reddit", "reddit.com": "reddit", "old.reddit.com": "reddit",
                        "hackernews": "hackernews", "hn": "hackernews",
                        "news.ycombinator.com": "hackernews"}

# the context a visitor arrives with: what onward clicks may be related to
PRE_VISIT = ("source", "referrer_domain", "utm_source", "utm_medium", "utm_campaign",
             "landing_path", "device_class", "country", "weekday", "hour")

PROBE_PREFIXES = ("/wp-", "/wordpress", "/xmlrpc.php", "/sitemap", "/.env", "/.git", "/admin",
                  "/phpmyadmin", "/airdrops", "/cgi-bin", "/vendor/", "/.well-known/security.txt",
                  "/account/login", "/auth/", "/app", "/config")

SEARCH_HOSTS = ("google.", "bing.com", "duckduckgo.com", "yahoo.", "ecosia.org", "yandex.",
                "baidu.com", "search.brave.com", "startpage.com")
SOCIAL_HOSTS = {"linkedin.com": "linkedin", "lnkd.in": "linkedin",
                "news.ycombinator.com": "hackernews", "reddit.com": "reddit",
                "old.reddit.com": "reddit", "x.com": None, "twitter.com": None, "t.co": None,
                "facebook.com": None, "bsky.app": None, "mastodon.social": None}
# domains a utm value may name as is (utm_source=linkedin.com): the social
# hosts and the search engines' own domains. Any other value with a dot is
# <invalid>, so a person's domain or an email never lands.
KNOWN_UTM_DOMAINS = set(SOCIAL_HOSTS) | {"google.com", "bing.com", "duckduckgo.com",
                                         "ecosia.org", "baidu.com", "search.brave.com",
                                         "startpage.com"}
MEDIUM_SOURCES = {"social": "social", "email": "email", "newsletter": "email",
                  "cpc": "paid", "ppc": "paid", "paid": "paid", "paid_social": "paid",
                  "referral": "referral", "organic": "organic"}
OS_DEVICES = {"ios": "mobile", "android": "mobile", "ipados": "tablet",
              "windows": "desktop", "mac os x": "desktop", "macos": "desktop",
              "linux": "desktop", "chrome os": "desktop", "ubuntu": "desktop"}

EMAIL = re.compile(r"[^/@\s]+@[^/@\s]+")
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
HEX_RUN = re.compile(r"[0-9a-fA-F]{16,}")
ALNUM_RUN = re.compile(r"[A-Za-z0-9]{16,}")
B64_RUN = re.compile(r"[A-Za-z0-9_-]{24,}")
UTM_VALUE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
STALE_DAYS = 2      # a newest stored day older than this fails the run


def _is_token(text: str) -> bool:
    """A secret-looking string: a UUID, a JWT, 16+ hex with a digit, 16+
    mixed-case alphanumerics with a digit, or 24+ base64url characters with
    an uppercase letter and a digit. Lowercase slugs (with - or _) are not."""
    if UUID.search(text) or JWT.search(text):
        return True
    if any(re.search(r"\d", m) for m in HEX_RUN.findall(text)):
        return True
    mixed = lambda m: re.search(r"\d", m) and re.search(r"[A-Z]", m) and re.search(r"[a-z]", m)
    return any(mixed(m) for m in ALNUM_RUN.findall(text)) or any(
        re.search(r"\d", m) and re.search(r"[A-Z]", m) for m in B64_RUN.findall(text))


def _strip_query(url: str) -> str:
    """The URL or path cut at its query string and fragment."""
    return url.split("#", 1)[0].split("?", 1)[0]


def _redact_segment(segment: str) -> str:
    """A path segment, or <email>/<token> when it carries one, judged after
    percent-decoding (so %40 is an @)."""
    decoded = unquote(segment)
    if EMAIL.search(decoded):
        return "<email>"
    if _is_token(decoded):
        return "<token>"
    return segment


def _redact_path(path: str) -> str:
    return "/".join(_redact_segment(s) for s in path.split("/"))


def _clean_utm(value: str | None) -> str | None:
    """A utm value, lowercased, spaces as _; <invalid> when it isn't a short
    plain slug of a-z, 0-9, - and _ (an email, a token, a 90-character
    string) or one of KNOWN_UTM_DOMAINS."""
    if value is None:
        return None
    value = value.strip().lower().replace(" ", "_")
    if value in KNOWN_UTM_DOMAINS:
        return value
    return value if UTM_VALUE.fullmatch(value) and not _is_token(value) else "<invalid>"


def _keyed(text: str) -> str:
    """HMAC-SHA256 of `text` with COMPANY_AI_WEB_SALT, 16 hex (docs/36).
    Without the salt the keys could be recomputed by anyone holding the
    Amplitude export, so a missing salt raises, never a bare-hash fallback."""
    salt = os.environ.get("COMPANY_AI_WEB_SALT")
    assert salt, "COMPANY_AI_WEB_SALT is not set: the web keys are salted (docs/36)"
    return hmac.new(salt.encode(), text.encode(), hashlib.sha256).hexdigest()[:16]


def _session_key(session_id, device_id) -> str:
    return _keyed(f"{session_id}:{device_id}")


def _visitor_key(device_id) -> str:
    """One browser: the same across its sessions. Journeys stay per browser,
    never joined across an account's browsers (Antti, 6.11.2026)."""
    return _keyed(f"visitor:{device_id}")


# the labels _source returns besides MEDIUM_SOURCES' values
_SOURCE_LABELS = {"other", "direct", "organic", "social", "referral"}


def _vocabulary_problems(medium_sources: dict, os_devices: dict) -> list[str]:
    """Labels the classification tables can produce that the web_sessions
    vocabularies don't hold. Checked at import, so a mismatch fails the
    books rather than a real day (2026-11-03 failed on one)."""
    problems = [f"source {label!r} (from utm_medium {medium!r}) is not in WEB_SESSION_SOURCES"
                for medium, label in medium_sources.items()
                if label not in schema.WEB_SESSION_SOURCES]
    problems += [f"source {label!r} is not in WEB_SESSION_SOURCES"
                 for label in sorted(_SOURCE_LABELS - schema.WEB_SESSION_SOURCES)]
    problems += [f"device_class {label!r} (from device_family {family!r}) is not in DEVICE_CLASSES"
                 for family, label in os_devices.items()
                 if label not in schema.DEVICE_CLASSES]
    if "unknown" not in schema.DEVICE_CLASSES:
        problems.append("device_class 'unknown' is not in DEVICE_CLASSES")
    return problems


_problems = _vocabulary_problems(MEDIUM_SOURCES, OS_DEVICES)
assert not _problems, _problems


def _host(url: str | None) -> str | None:
    if not url:
        return None
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host or None


def _page_kind(event: dict) -> str | None:
    etype = event["event_type"]
    for kind, prefix in PAGE_VIEW_PREFIXES.items():
        if etype.startswith(prefix):
            return kind
    return None


def _page(event: dict) -> str | None:
    """The page an event viewed, query and fragment dropped, sensitive
    segments redacted, other hosts host-first. None when the event names no
    path (counted by the caller, never guessed)."""
    props = event.get("event_properties") or {}
    path = props.get("[Amplitude] Page Path") or props.get("path")
    if path is None and event["event_type"].startswith("Page View: "):
        path = event["event_type"][len("Page View: "):]
    if not path:
        return None
    path = _redact_path(_strip_query(path))
    host = (props.get("[Amplitude] Page Domain") or SITE_HOST).lower()
    host = host[4:] if host.startswith("www.") else host
    return path if host == SITE_HOST else f"{host}{path}"


def _event_kpis(event: dict) -> list[str]:
    """The KPIs one event reaches: by its name (KPI_EVENTS), or for a page
    view by its host and path (KPI_PAGES)."""
    page = _page(event) if _page_kind(event) is not None else None
    return [k for k in KPI_EVENTS
            if event["event_type"] in KPI_EVENTS[k] or (page is not None and page in KPI_PAGES.get(k, ()))]


def _event_token(event: dict) -> str | None:
    """One event as a token for the `events` field: a page view is
    `page:<page>` (redacted like `pages`), anything else its event NAME
    snake-cased to [a-z0-9_]. Never a property value."""
    if _page_kind(event) is not None:
        page = _page(event)
        return f"page:{page}" if page else None
    token = re.sub(r"[^a-z0-9]+", "_", event["event_type"].lower()).strip("_")[:64]
    return token or None


def _device_class(family: str | None) -> str:
    """From the export's device_family, which is the OS (Windows, Mac OS X,
    iOS); its os_name is the browser."""
    return OS_DEVICES.get((family or "").lower(), "unknown")


def _referrer(props: dict) -> str | None:
    """The host a session arrived from: the first page view's previous page,
    when the SDK marks it external. Direct and internal arrivals have none.
    Only the host is kept, never the other site's path or query, and a host
    with a token-like label (a per-visitor tracking subdomain) is <token>."""
    if props.get("[Amplitude] Previous Page Type") != "external":
        return None
    host = _host(props.get("[Amplitude] Previous Page Location"))
    if host and any(_is_token(label) or EMAIL.search(label) for label in host.split(".")):
        return "<token>"
    return host


def _source(medium: str | None, referrer: str | None) -> str:
    if medium:
        return MEDIUM_SOURCES.get(medium, "other")
    if not referrer or referrer == SITE_HOST or referrer.endswith("." + SITE_HOST):
        return "direct"
    if any(referrer.startswith(h) or ("." + h) in referrer for h in SEARCH_HOSTS):
        return "organic"
    if referrer in SOCIAL_HOSTS:
        return "social"
    return "referral"


def _time(event: dict) -> datetime:
    return datetime.fromisoformat(event["event_time"][:19])


def _sessions(events: list[dict]) -> dict:
    """Events grouped by session; an event with no session is its own."""
    by_session: dict = {}
    for event in events:
        sid, did = event.get("session_id"), event.get("device_id")
        key = (sid, did, event.get("$insert_id")) if sid in NO_SESSION else (sid, did)
        by_session.setdefault(key, []).append(event)
    return by_session


def _build(events: list[dict], day: str) -> tuple[list[dict], dict]:
    """The rows for the sessions whose first event is on `day` (UTC), and
    the run's counts over those sessions' events."""
    rows: list[dict] = []
    stats = {"mapped": Counter(), "unmapped": Counter(), "unknown_os": Counter(),
             "no_session_events": 0, "utm_present": 0, "referrer_present": 0, "invalid_utm": 0,
             "new_event_types": Counter(),
             "events_on_day": sum(e["event_time"][:10] == day for e in events)}
    for key, group in _sessions(events).items():
        group.sort(key=_time)
        start = _time(group[0])
        if start.date().isoformat() != day:
            continue
        if key[0] in NO_SESSION:
            stats["no_session_events"] += 1
        views, pages = [], []
        for e in group:
            kind = _page_kind(e)
            if kind is None:
                name = e["event_type"]
                if not name.endswith(CTA_SUFFIX):
                    stats["unmapped"][name] += 1
                    if name not in LIFECYCLE_EVENTS | KNOWN_EVENT_TYPES | _KPI_EVENT_NAMES:
                        stats["new_event_types"][name] += 1
                continue
            page = _page(e)
            if page is None:
                stats["unmapped"][f"{kind} (no path)"] += 1
                continue
            stats["mapped"][kind] += 1
            views.append(e)
            pages.append(page)
        if not views:
            continue
        first = views[0]
        props = first.get("event_properties") or {}
        # the export's Page URL has its query string stripped; Page Location keeps it
        url = props.get("[Amplitude] Page Location") or props.get("[Amplitude] Page URL") or ""
        query = parse_qs(urlsplit(url).query)
        utm = {k: _clean_utm((query.get(k) or [None])[0])
               for k in ("utm_source", "utm_medium", "utm_campaign")}
        stats["utm_present"] += any(utm.values())
        stats["invalid_utm"] += sum(v == "<invalid>" for v in utm.values())
        referrer = _referrer(props)
        stats["referrer_present"] += referrer is not None
        ctas = [e for e in group if e["event_type"].endswith(CTA_SUFFIX)]
        device = _device_class(first.get("device_family"))
        if device == "unknown":
            stats["unknown_os"][str(first.get("device_family"))] += 1
        medium = utm["utm_medium"] if utm["utm_medium"] != "<invalid>" else None
        # each event of the visit as (token, the KPIs its NAME belongs to)
        steps = [(tok, _event_kpis(e))
                 for e in group if e["event_type"] not in LIFECYCLE_EVENTS
                 for tok in [_event_token(e)] if tok]
        reached = {k for e in group for k in _event_kpis(e)}
        tokens = [tok for tok, _ in steps]
        rows.append({
            "session_key": _session_key(*key[:2]) if key[0] not in NO_SESSION
            else _session_key(key[0], f"{key[1]}:{key[2]}"),
            "visitor_key": _visitor_key(key[1]),
            # every event of the visit, in order, and its mirror for
            # co-occurrence relations (docs/36), plus one flag per KPI
            "events": " ".join(tokens) or None,
            "co_events": " ".join(tokens) or None,
            "_steps": steps,           # popped by store_day into web_steps (docs/37)
            **{f"kpi_{kpi}": kpi in reached for kpi in KPI_EVENTS},
            "day": day, "hour": start.hour,
            "weekday": schema.WEEKDAYS[start.weekday()],
            "week": f"{start.isocalendar().year}-W{start.isocalendar().week:02d}",
            "landing_path": pages[0],
            "next_path": pages[1] if len(pages) > 1 else None,
            "pages": " ".join(pages),
            "views": len(pages),
            "engaged_seconds": int((_time(group[-1]) - start).total_seconds()),
            "onward_click": len(pages) > 1 or bool(ctas),
            "signup_cta": bool(ctas) or any(p.startswith(SIGNUP_PATHS) for p in pages),
            "referrer_domain": referrer,
            "source": _source(medium, referrer),
            **utm,
            "device_class": device,
            "country": first.get("country") or "unknown",
            # a probe page anywhere in the visit, not only the landing: crawlers
            # fetch the sitemaps mid-visit (first real paths run, 6.11.2026)
            "likely_bot": any(p.startswith(PROBE_PREFIXES) for p in pages),
            "post_id": None, "candidate_post_id": None, "matched_post_id": None,
            "experiment_id": None,
            "link_basis": None,
        })
    return rows, stats


def sessions_from_events(events: list[dict], day: str) -> list[dict]:
    """One row per session that started on `day` and has a page view, built
    field by field. Links are filled in by `store_day`. The internal `_steps`
    (store_day's input for web_steps) is left out: its tokens are `events`."""
    return [{k: v for k, v in r.items() if k != "_steps"} for r in _build(events, day)[0]]


def _link(client: AitoClient, rows: list[dict], day: str) -> dict:
    """Fill the links. Exact: (utm_campaign, the platform utm_source names) is
    one post (post_id); a tag on a single platform also matches a visit with
    no recognised source; or utm_campaign is an experiment_id. Candidate:
    exactly one post on the referrer's platform in the LOOKBACK_DAYS before
    (candidate_post_id). A visit before the post went out is never credited;
    a (tag, platform) two posts share links nothing. Returns what was
    refused, by kind."""
    posts = client.query({"from": "posts", "limit": 100000,
                          "select": ["post_id", "platform", "status", "posted_at", "utm_campaign",
                                     "link_path"]})["hits"]
    by_campaign: dict[str, list[dict]] = {}
    for p in posts:
        if p.get("utm_campaign"):
            by_campaign.setdefault(p["utm_campaign"], []).append(p)
    experiments = {e["experiment_id"] for e in client.query(
        {"from": "experiments", "limit": 100000, "select": ["experiment_id"]})["hits"]}
    by_key: dict[tuple, list[str]] = {}
    for slug, ps in by_campaign.items():
        for p in ps:
            by_key.setdefault((slug, p.get("platform")), []).append(p["post_id"])
    duplicates = {f"{slug}|{plat}": sorted(ids) for (slug, plat), ids in by_key.items()
                  if len(ids) > 1}
    start = (date.fromisoformat(day) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    before_post = ambiguous = 0
    for row in rows:
        if row["likely_bot"]:
            continue
        campaign = row["utm_campaign"]
        if campaign and campaign in by_campaign:
            tagged = by_campaign[campaign]
            platform = UTM_SOURCE_PLATFORMS.get(row.get("utm_source") or "")
            if platform:
                matches = [p for p in tagged if p.get("platform") == platform]
            else:     # no recognised source: only a tag on a single platform is unambiguous
                matches = tagged if len({p.get("platform") for p in tagged}) == 1 else []
            if len(matches) == 1:
                post = matches[0]
                if (post.get("posted_at") or "9999")[:10] > day:
                    before_post += 1
                else:
                    row["post_id"], row["link_basis"] = post["post_id"], "utm_campaign"
        if campaign and campaign in experiments:
            row["experiment_id"], row["link_basis"] = campaign, "utm_campaign"
        if row["link_basis"] or (campaign and campaign in by_campaign):
            continue
        platform = SOCIAL_HOSTS.get(row["referrer_domain"] or "")
        if not platform:
            continue
        # tier 2: the post's platform, its page, within MATCH_DAYS of posting
        fits = [p for p in posts if p.get("platform") == platform and p.get("status") == "posted"
                and p.get("link_path") == row["landing_path"] and p.get("posted_at")
                and p["posted_at"][:10] <= day <= (date.fromisoformat(p["posted_at"][:10])
                                                  + timedelta(days=MATCH_DAYS)).isoformat()]
        if len(fits) == 1:
            row["matched_post_id"], row["link_basis"] = fits[0]["post_id"], "referrer_landing"
            continue
        if len(fits) > 1:
            ambiguous += 1
            continue
        # posts with a link_path are matched by it, never guessed by day alone
        near = [p for p in posts if p.get("platform") == platform and p.get("status") == "posted"
                and not p.get("link_path") and start <= (p.get("posted_at") or "")[:10] <= day]
        if len(near) == 1:
            row["candidate_post_id"], row["link_basis"] = near[0]["post_id"], "referrer_day"
    return {"duplicate_campaigns": duplicates, "before_post": before_post,
            "ambiguous_matches": ambiguous}


def store_day(client: AitoClient, day: str, events: list[dict]) -> dict:
    """Make `day`'s web_sessions rows the sessions in `events` that started
    on it. The new rows are uploaded under a fresh pull_run and checked
    before the old runs' rows are deleted, so a failed upload leaves the day
    as it was. A day with no sessions keeps any rows it had and is flagged
    empty. Returns the run's report."""
    date.fromisoformat(day)
    rows, stats = _build(events, day)
    # browsers deleted on request stay out (docs/36)
    suppressed = {h["visitor_key"] for h in client.query(
        {"from": "web_suppressed", "select": ["visitor_key"], "limit": 1_000_000})["hits"]}
    kept = [r for r in rows if r["visitor_key"] not in suppressed]
    stats["suppressed"] = len(rows) - len(kept)
    rows = kept
    refused = _link(client, rows, day)
    run = uuid.uuid4().hex[:12]
    for r in rows:
        assert r["source"] in schema.WEB_SESSION_SOURCES and r["device_class"] in schema.DEVICE_CLASSES, r
        r["pull_run"] = run
    steps = _steps(client, rows, run)
    old = {r.get("pull_run") for r in client.query(
        {"from": "web_sessions", "where": {"day": day}, "select": ["pull_run"], "limit": 100000})["hits"]}
    kept = 0
    if rows:
        old_steps = {h.get("pull_run") for h in client.query(
            {"from": "web_steps", "where": {"day": day}, "select": ["pull_run"],
             "limit": 1_000_000})["hits"]}
        client.upload_batch("web_sessions", rows)
        try:
            for i in range(0, len(steps), UPLOAD_CHUNK):
                client.upload_batch("web_steps", steps[i:i + UPLOAD_CHUNK])
            landed = client.query({"from": "web_sessions", "where": {"day": day, "pull_run": run},
                                   "limit": 0})["total"]
            assert landed == len(rows), f"web_sessions {day}: {landed} of {len(rows)} rows landed"
            landed = client.query({"from": "web_steps", "where": {"day": day, "pull_run": run},
                                   "limit": 0})["total"]
            assert landed == len(steps), f"web_steps {day}: {landed} of {len(steps)} steps landed"
            for previous in sorted(p for p in old if p):
                client.delete_entries("web_sessions", {"day": day, "pull_run": previous})
            for previous in sorted(p for p in old_steps if p):
                client.delete_entries("web_steps", {"day": day, "pull_run": previous})
        except Exception:
            # the old rows stay the day's rows; the new run must not double it
            client.delete_entries("web_sessions", {"day": day, "pull_run": run})
            client.delete_entries("web_steps", {"day": day, "pull_run": run})
            raise
    else:
        kept = client.query({"from": "web_sessions", "where": {"day": day}, "limit": 0})["total"]
    linked = Counter(r["link_basis"] for r in rows if r["link_basis"])
    return {"day": day, "pull_run": run, "events": len(events), "sessions": len(rows),
            "steps": len(steps),
            "empty": not rows, "kept_previous": kept,
            "bots": sum(r["likely_bot"] for r in rows), "linked": dict(linked),
            "mapped": dict(stats["mapped"]), "unmapped": dict(stats["unmapped"]),
            "unknown_os": dict(stats["unknown_os"]),
            "new_event_types": dict(stats["new_event_types"]),
            "no_session_events": stats["no_session_events"],
            "suppressed": stats["suppressed"],
            "events_on_day": stats["events_on_day"],
            "utm_present": stats["utm_present"], "referrer_present": stats["referrer_present"],
            "invalid_utm": stats["invalid_utm"],
            # a page on another host is written host-first, not starting with "/"
            "multi_host_sessions": sum(any(not p.startswith("/") for p in r["pages"].split())
                                       for r in rows),
            **refused}


def events_from_export(blob: bytes) -> list[dict]:
    """The events in an Export API response: a zip of gzipped JSON-lines
    files. Read in memory; nothing is written to disk."""
    events = []
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for name in sorted(archive.namelist()):
            for line in gzip.decompress(archive.read(name)).decode().splitlines():
                if line.strip():
                    events.append(json.loads(line))
    return events


def fetch_day(day: str, now: datetime | None = None) -> list[dict]:
    """The events from the day before `day` to the day after, so a session
    that started on `day` is whole, and one that started the day before is
    seen as such. The Export API may select by upload time rather than event
    time (docs/35); the wide window covers late uploads too. The keys come
    from the environment (AMPLITUDE_API_KEY, AMPLITUDE_SECRET_KEY), placed by
    the operator; they are used for the request and never logged. No data is
    an empty list (Amplitude answers 404). The window's end is clamped to the
    current hour: what the API does with an end in the future is unverified,
    so it is never sent one."""
    key, secret = os.environ.get("AMPLITUDE_API_KEY"), os.environ.get("AMPLITUDE_SECRET_KEY")
    assert key and secret, "AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY are not set (docs/35)"
    d = date.fromisoformat(day)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(tzinfo=None)
    start = datetime.combine(d - timedelta(days=1), datetime.min.time())
    end = min(datetime.combine(d + timedelta(days=1), datetime.min.time()) + timedelta(hours=23),
              now.replace(minute=0, second=0, microsecond=0))
    response = requests.get(EXPORT_URL, params={"start": start.strftime("%Y%m%dT%H"),
                                                "end": end.strftime("%Y%m%dT%H")},
                            auth=(key, secret), timeout=300)
    if response.status_code == 404:
        return []
    assert response.status_code == 200, \
        f"Amplitude export {day}: HTTP {response.status_code} {response.text[:200]}"
    return events_from_export(response.content)


class PullLocked(RuntimeError):
    """Another pull of the same instance is running."""


@contextmanager
def pull_lock(client: AitoClient):
    """One pull per instance at a time: the timer and a manual run would
    each upload a day before either deletes, doubling it until the next pull.
    A lock file in the temp directory, keyed by the instance URL."""
    tag = hashlib.sha256(str(getattr(client, "base_url", "")).encode()).hexdigest()[:12]
    path = Path(tempfile.gettempdir()) / f"company-ai-web-pull-{tag}.lock"
    with open(path, "w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise PullLocked(f"another pull-web is running (lock {path})") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def health(reports: list[dict], newest: str | None, today: date) -> tuple[list[str], list[str]]:
    """(problems, warnings) for a run. Problems fail it: a day that errored,
    a day with events but no sessions (tracking renamed or the parser
    looking in the wrong place), and a table whose newest day is more than
    STALE_DAYS old. A day with no events at all is only a warning."""
    problems, warnings = [], []
    for r in reports:
        if r.get("error"):
            problems.append(f"{r['day']}: {r['error']}")
        elif r.get("events_on_day") and not r.get("sessions"):
            problems.append(f"{r['day']}: {r['events_on_day']} events but no sessions: "
                            "page-view events renamed, or not where the parser looks")
        elif r.get("empty"):
            warnings.append(f"{r['day']}: no visits pulled")
        if r.get("new_event_types"):
            names = ", ".join(sorted(r["new_event_types"]))
            warnings.append(f"{r['day']}: event names never seen before, not in any KPI: {names} "
                            "(add each to KPI_EVENTS or KNOWN_EVENT_TYPES, docs/36)")
    if newest is None:
        problems.append("web_sessions holds no day at all")
    elif date.fromisoformat(newest) < today - timedelta(days=STALE_DAYS):
        problems.append(f"newest stored day is {newest}, more than {STALE_DAYS} days old")
    return problems, warnings


def pull(client: AitoClient, days: int = LOOKBACK_DAYS, day: str | None = None,
         today: date | None = None, fetch=fetch_day) -> list[dict]:
    """Pull `day`, or the last `days` complete UTC days, into web_sessions.
    Each day is stored on its own: a day that fails is reported with its
    error and the rest still run."""
    if day:
        wanted = [day]
    else:
        today = today or datetime.now(timezone.utc).date()
        wanted = [(today - timedelta(days=n)).isoformat() for n in range(days, 0, -1)]
    reports = []
    with pull_lock(client):
        for d in wanted:
            try:
                reports.append(store_day(client, d, fetch(d)))
            except Exception as e:  # noqa: BLE001 — reported per day; the caller exits non-zero
                reports.append({"day": d, "error": f"{type(e).__name__}: {e}"})
        # retention: days older than 13 months go (docs/36)
        try:
            reports.append({"day": "retention", **prune_old_days(client, today or
                                                                  datetime.now(timezone.utc).date())})
        except Exception as e:  # noqa: BLE001
            reports.append({"day": "retention", "error": f"{type(e).__name__}: {e}"})
        # the visitor view follows the sessions; a failure is reported like a day's
        try:
            reports.append({"day": "web_visitors", **build_visitors(client)})
        except Exception as e:  # noqa: BLE001
            reports.append({"day": "web_visitors", "error": f"{type(e).__name__}: {e}"})
    return reports


def _top(counts: Counter, n: int = 10) -> list:
    """The n most frequent values, ties in value order."""
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def _window(since: str, until: str) -> list[dict]:
    return [{"day": {"$gte": since}}, {"day": {"$lte": until}}]


def _rows(client: AitoClient, since: str, until: str, select: list[str], where: dict | None = None):
    clauses = [*_window(since, until), *(
        {k: v} for k, v in (where or {}).items() if v is not None)]
    return client.query({"from": "web_sessions", "where": {"$and": clauses},
                         "select": select, "limit": 100000})["hits"]


def web_traffic(client: AitoClient, since: str, until: str, path: str | None = None,
                campaign: str | None = None, source: str | None = None) -> dict:
    """Per-day sessions, views, onward clicks and sign-up CTAs (bots counted
    apart), the top landing pages and sources, the posts the visits link to
    exactly, and the candidate posts apart."""
    rows = _rows(client, since, until, ["day", "views", "onward_click", "signup_cta", "likely_bot",
                                         "landing_path", "source", "post_id", "candidate_post_id",
                                         "matched_post_id"],
                 {"landing_path": path, "utm_campaign": campaign, "source": source})
    human = [r for r in rows if not r["likely_bot"]]
    days: dict = {}
    for r in human:
        d = days.setdefault(r["day"], {"day": r["day"], "sessions": 0, "views": 0,
                                       "onward_clicks": 0, "signup_ctas": 0})
        d["sessions"] += 1
        d["views"] += r["views"]
        d["onward_clicks"] += r["onward_click"]
        d["signup_ctas"] += r["signup_cta"]
    return {"since": since, "until": until, "days": [days[d] for d in sorted(days)],
            "bots": len(rows) - len(human),
            "top_landing": _top(Counter(r["landing_path"] for r in human)),
            "top_sources": _top(Counter(r["source"] for r in human)),
            "posts": [{"post_id": p, "sessions": n} for p, n in
                      _top(Counter(r["post_id"] for r in human if r.get("post_id")), 50)],
            "candidate_posts": [{"post_id": p, "sessions": n} for p, n in
                                _top(Counter(r["candidate_post_id"] for r in human
                                             if r.get("candidate_post_id")), 50)],
            "matched_posts": [{"post_id": p, "sessions": n} for p, n in
                              _top(Counter(r["matched_post_id"] for r in human
                                           if r.get("matched_post_id")), 50)],
            # the tiers apart, never merged; tier 3 waits for enough labels
            "attribution": _attribution(human)}


def _attribution(human: list[dict]) -> dict:
    """Sessions per attribution tier (docs/35), and whether tiers 1-2 have
    labelled enough sessions for tier 3 (INFERENCE_TRIGGER)."""
    exact = sum(bool(r.get("post_id")) for r in human)
    matched = sum(bool(r.get("matched_post_id")) for r in human)
    return {"exact": exact, "matched": matched,
            "candidates": sum(bool(r.get("candidate_post_id")) for r in human),
            "labels": exact + matched, "inference_trigger": INFERENCE_TRIGGER,
            "inference_ready": exact + matched >= INFERENCE_TRIGGER}


def web_paths(client: AitoClient, since: str, until: str, landing_path: str | None = None,
              source: str | None = None, device_class: str | None = None) -> dict:
    """Landing -> next path counts by source and device, per ISO week (bots
    excluded). A session that ended on its landing page has next_path null."""
    rows = _rows(client, since, until,
                 ["week", "landing_path", "next_path", "source", "device_class", "likely_bot"],
                 {"landing_path": landing_path, "source": source, "device_class": device_class})
    counts = Counter((r["week"], r["landing_path"], r.get("next_path"), r["source"], r["device_class"])
                     for r in rows if not r["likely_bot"])
    return {"since": since, "until": until, "paths": [
        {"week": w, "landing_path": lp, "next_path": np, "source": s, "device_class": dc,
         "sessions": n} for (w, lp, np, s, dc), n in sorted(
            counts.items(), key=lambda kv: (kv[0][0], -kv[1], kv[0][1], kv[0][2] or "", kv[0][3], kv[0][4]))]}


def predict_next_path(client: AitoClient, landing_path: str, source: str | None = None,
                      device_class: str | None = None, limit: int = 5) -> tuple[dict, dict]:
    """Aito's P(next page | how the visitor arrived), with $why — the front
    page's recommendation source. Thin data shows as low $p."""
    where = {"landing_path": landing_path, "likely_bot": False,
             **({"source": source} if source else {}),
             **({"device_class": device_class} if device_class else {})}
    request = {"from": "web_sessions", "where": where, "predict": "next_path",
               "select": ["$p", "$value", "$why"], "limit": limit}
    return request, client.predict(request)


def onward_drivers(client: AitoClient, since: str, until: str, path: str | None = None,
                   top_n: int = 10) -> dict:
    """Which pre-visit context (PRE_VISIT: source, referrer, utm, landing
    page, device, country, weekday, hour) goes with an onward click: Aito's
    _relate over human sessions in the window. What happened during the
    visit (next path, views, CTAs) defines the click, so relations exclude it."""
    where = {"likely_bot": False, "$and": _window(since, until)}
    if path:
        where["landing_path"] = path
    return relations.relate(client, "web_sessions", {"onward_click": True},
                            where=where, top_n=top_n)


# ---- the dashboard's Web view: one bundle per filter ----

# Below this many sessions a relation is shown as "thin, no claim" instead of
# a lift. Antti chose 5 (6.11.2026, docs/36): conversions are rare, and the
# relate tool's 10 would hide nearly every sign-up insight.
WEB_THIN = 5

# the visit-level outcomes a Web view tile relates (docs/44 slice 1)
VIEW_OUTCOMES = ("onward_click", "signup_cta")

WEB_VIEW_FIELDS = ["day", "hour", "landing_path", "next_path", "source", "referrer_domain",
                   "utm_campaign", "post_id", "device_class", "country", "views",
                   "engaged_seconds", "onward_click", "signup_cta", "likely_bot"]


def web_view(client: AitoClient, since: str, until: str, source: str | None = None,
             campaign: str | None = None, path: str | None = None, device: str | None = None,
             limit: int = 25, offset: int = 0, outcome: str = "onward_click") -> dict:
    """What the Web view shows for one filter.
    - totals and the per-day series: counts over the matching human sessions;
    - facets: the filter choices, from the whole window, so a chosen filter
      doesn't hide the alternatives;
    - drivers: Aito's _relate of the chosen visit outcome (VIEW_OUTCOMES:
      onward_click or signup_cta) over the same population;
    - next_paths: Aito's _predict next_path when a landing page is chosen;
    - sessions: a page of the matching rows, newest first, bots included and
      flagged.
    Counting and paging are formatting; every relation and prediction is Aito's
    (rule 2)."""
    if outcome not in VIEW_OUTCOMES:
        raise AssertionError(f"unknown outcome {outcome!r}; the Web view relates {VIEW_OUTCOMES}")
    filt = {"source": source, "utm_campaign": campaign, "landing_path": path,
            "device_class": device}
    kpi_fields = [f"kpi_{k}" for k in KPI_EVENTS]
    rows = _rows(client, since, until, WEB_VIEW_FIELDS + kpi_fields, filt)
    human = [r for r in rows if not r["likely_bot"]]
    days: dict = {}
    for r in human:
        d = days.setdefault(r["day"], {"day": r["day"], "sessions": 0, "onward_clicks": 0,
                                       "signup_ctas": 0, **{f: 0 for f in kpi_fields}})
        d["sessions"] += 1
        d["onward_clicks"] += r["onward_click"]
        d["signup_ctas"] += r["signup_cta"]
        for f in kpi_fields:
            d[f] += bool(r.get(f))
    n = len(human)
    totals = {"sessions": n, "onward_clicks": sum(r["onward_click"] for r in human),
              "signup_ctas": sum(r["signup_cta"] for r in human), "bots": len(rows) - n}
    all_rows = rows if not any(filt.values()) else _rows(
        client, since, until, ["source", "utm_campaign", "landing_path", "device_class", "likely_bot"])
    all_human = [r for r in all_rows if not r["likely_bot"]]
    facets = {
        "source": sorted({r["source"] for r in all_human}),
        "device_class": sorted({r["device_class"] for r in all_human}),
        "utm_campaign": [v for v, _ in _top(Counter(r["utm_campaign"] for r in all_human
                                                    if r.get("utm_campaign")), 30)],
        "landing_path": [v for v, _ in _top(Counter(r["landing_path"] for r in all_human), 30)],
    }
    where = {"likely_bot": False, "$and": [*_window(since, until), *(
        {k: v} for k, v in filt.items() if v is not None)]}
    drivers = relations.relate(client, "web_sessions", {outcome: True},
                               where=where, top_n=10, thin=WEB_THIN) if n else None
    next_paths = None
    if path:
        request, response = predict_next_path(client, path, source=source, device_class=device)
        next_paths = {"request": request,
                      "hits": [{"value": h["$value"], "p": h["$p"]} for h in response.get("hits", [])]}
    ordered = sorted(rows, key=lambda r: (r["day"], r["hour"]), reverse=True)
    return {"since": since, "until": until,
            "filters": {k: v for k, v in filt.items() if v is not None},
            "totals": totals, "days": [days[d] for d in sorted(days)], "facets": facets,
            "thin_below": WEB_THIN,
            # human sessions that reached each KPI in the filter (docs/36)
            "kpis": {k: sum(bool(r.get(f"kpi_{k}")) for r in human) for k in KPI_EVENTS},
            "outcome": outcome, "drivers": drivers, "next_paths": next_paths,
            "session_total": len(rows), "sessions": ordered[offset:offset + limit]}


# ---- MCP web_kpis: one KPI or any event, related in Aito (docs/36) ----

# The console funnel: each step implies the visitor met the others, so a lift
# between them is definitional, not a driver. Relating one drops the rest.
CONSOLE_FUNNEL = ("login_page", "signup", "sandbox", "data_loaded", "first_query", "api_keys")
EVENT_TOKEN = re.compile(r"[a-z0-9_]{1,64}|page:\S{1,200}")


def _own_tokens(kpi: str) -> set[str]:
    """The event tokens that define a KPI, so "other events" doesn't restate it."""
    return {tok for tok in (_event_token({"event_type": name, "event_properties": {}})
                            for name in KPI_EVENTS[kpi]) if tok} \
        | {f"page:{page}" for page in KPI_PAGES.get(kpi, ())}


def web_kpis(client: AitoClient, kpi: str | None = None, event: str | None = None,
             since: str | None = None, until: str | None = None, source: str | None = None,
             campaign: str | None = None, path: str | None = None,
             device: str | None = None) -> dict:
    """For one preselected KPI (KPI_EVENTS) or any event token, over the human
    sessions in the window and filter:
    - how many sessions there were and how many had the target;
    - drivers: the pre-visit context related to it;
    - other_kpis: the other KPIs that go with it, minus the console-funnel
      steps that are definitionally linked (named in dropped_as_linked);
    - other_events: events that go with it, read from co_events, minus the
      target's own events (dropped_own_events).
    Every relation is Aito's _relate, carries its counts, and is flagged thin
    under WEB_THIN sessions (rule 2: no lift is computed here)."""
    assert (kpi is None) != (event is None), "give exactly one target: kpi or event"
    if kpi is not None:
        assert kpi in KPI_EVENTS, f"unknown kpi {kpi!r}; have {sorted(KPI_EVENTS)}"
        outcome, own = {f"kpi_{kpi}": True}, _own_tokens(kpi)
        match = outcome
        linked = [f"kpi_{k}" for k in CONSOLE_FUNNEL if k != kpi] if kpi in CONSOLE_FUNNEL else []
    else:
        assert EVENT_TOKEN.fullmatch(event), f"not an event token: {event!r}"
        # _relate takes the bare token (a top-level $has is rejected until
        # aito-core's fix); in `where`, a bare value on Text is whole-field
        # equality, so the count matches the token with $has
        outcome, own, linked = {"events": event}, {event}, []
        match = {"events": {"$has": event}}
    until = until or date.today().isoformat()
    since = since or (date.fromisoformat(until) - timedelta(days=29)).isoformat()
    filt = {"source": source, "utm_campaign": campaign, "landing_path": path, "device_class": device}
    clauses = [*_window(since, until), *({k: v} for k, v in filt.items() if v is not None)]
    where = {"likely_bot": False, "$and": clauses}
    count = lambda w: client.query({"from": "web_sessions", "where": w, "limit": 0})["total"]
    sessions = count(where)
    with_target = count({**where, "$and": [*clauses, match]})
    out = {"target": {"kpi": kpi} if kpi else {"event": event}, "since": since, "until": until,
           "filters": {k: v for k, v in filt.items() if v is not None},
           "sessions": sessions, "with_target": with_target, "thin_below": WEB_THIN,
           "dropped_as_linked": linked, "dropped_own_events": sorted(own),
           "drivers": None, "other_kpis": None, "other_events": None,
           "acquisition": None, "journeys": []}
    if not with_target:
        out["note"] = "no session in the window had the target: nothing to relate"
        return out
    rel = lambda **kw: relations.relate(client, "web_sessions", outcome, where=where,
                                        thin=WEB_THIN, **kw)
    out["drivers"] = rel(top_n=10)
    # the relate and the count must agree on who has the target: they read
    # Text differently, so a disagreement raises instead of returning lifts
    assert out["drivers"]["with_outcome"] in (0, with_target), \
        f"_relate counted {out['drivers']['with_outcome']} sessions with {outcome}, the query {with_target}"
    kpi_fields = [f"kpi_{k}" for k in KPI_EVENTS if f"kpi_{k}" not in linked and k != kpi]
    others = rel(top_n=50, keep=kpi_fields)
    others["relations"] = [r for r in others["relations"] if r["field"] in kpi_fields][:10]
    out["other_kpis"] = others
    events = rel(top_n=50, keep=["co_events"])
    events["relations"] = [r for r in events["relations"]
                           if r["field"] == "co_events" and r["value"] not in own][:10]
    out["other_events"] = events
    if kpi is not None:
        out["acquisition"] = _acquisition(client, kpi)
    out["journeys"] = _journeys(client, {**where, "$and": [*clauses, match]})
    return out


JOURNEYS = 5           # the latest sessions with the target
JOURNEY_DEPTH = 10     # earlier sessions shown per browser


def _acquisition(client: AitoClient, kpi: str) -> dict | None:
    """Over all stored visitors (web_visitors, lifetime, not the window):
    which first touch, and which events seen before the first KPI, go with
    reaching `kpi`. Aito's _relate, with counts and the thin flag. A KPI no
    visitor reached has nothing to relate."""
    target = {f"kpi_{kpi}": True}
    if not client.query({"from": "web_visitors", "where": target, "limit": 0})["total"]:
        return None
    return relations.relate(client, "web_visitors", target, top_n=10, thin=WEB_THIN,
                            keep=["seen_before_first_kpi"])


def _journeys(client: AitoClient, where: dict) -> list[dict]:
    """The latest sessions matching `where`, each with its browser's earlier
    sessions, oldest first. Labelled by number: the visitor_key never leaves
    the database in a journey."""
    fields = ["visitor_key", "day", "hour", "landing_path", "source", "events"]
    latest = client.query({"from": "web_sessions", "where": where, "select": fields,
                           "orderBy": {"$desc": "day"}, "limit": JOURNEYS})["hits"]
    histories = client.batch([{"from": "web_sessions", "select": fields[1:],
                               "where": {"visitor_key": s["visitor_key"], "likely_bot": False,
                                         "day": {"$lte": s["day"]}},
                               "limit": 1000} for s in latest])
    out = []
    for n, (s, hist) in enumerate(zip(latest, histories), 1):
        upto = sorted((h for h in hist["hits"] if (h["day"], h["hour"]) <= (s["day"], s["hour"])),
                      key=lambda h: (h["day"], h["hour"]))[-JOURNEY_DEPTH:]
        out.append({"label": f"visitor {n}",
                    "sessions": [{k: h.get(k) for k in fields[1:]} for h in upto]})
    return out


# ---- web_visitors: one row per browser (docs/36 phase 2) ----

VISITOR_SOURCE_FIELDS = ["visitor_key", "session_key", "day", "hour", "source", "referrer_domain",
                         "utm_source", "utm_medium", "utm_campaign", "landing_path",
                         "device_class", "country", "post_id", "events",
                         *[f"kpi_{k}" for k in KPI_EVENTS]]
UPLOAD_CHUNK = 1000


def _visitor_row(sessions: list[dict], run: str) -> dict:
    """One browser's row from its human sessions, oldest first. Grouping and
    first/any is formatting; nothing here predicts (rule 2)."""
    first = sessions[0]
    kpi_days = {k: next((s["day"] for s in sessions if s.get(f"kpi_{k}")), None)
                for k in KPI_EVENTS}
    first_kpi = next((i for i, s in enumerate(sessions)
                      if any(s.get(f"kpi_{k}") for k in KPI_EVENTS)), len(sessions))
    seen: list[str] = []
    for s in sessions[:first_kpi]:
        for tok in (s.get("events") or "").split():
            if tok not in seen:
                seen.append(tok)
    return {
        "visitor_key": first["visitor_key"], "first_day": first["day"],
        "last_day": sessions[-1]["day"], "sessions": len(sessions),
        **{f"first_{k}": first.get(k) for k in ("source", "referrer_domain", "utm_source",
                                                 "utm_medium", "utm_campaign", "landing_path",
                                                 "device_class", "country")},
        "first_post_id": first.get("post_id"),
        "seen_before_first_kpi": " ".join(seen) or None,
        **{f"kpi_{k}": d is not None for k, d in kpi_days.items()},
        **{f"first_kpi_day_{k}": d for k, d in kpi_days.items()},
        "pull_run": run,
    }


def build_visitors(client: AitoClient) -> dict:
    """Rebuild web_visitors from the human web_sessions: upload the new run,
    check every row landed, then delete the earlier runs. A failure after the
    upload deletes the new run, so the table never doubles (as store_day)."""
    hits = client.query({"from": "web_sessions", "where": {"likely_bot": False},
                         "select": VISITOR_SOURCE_FIELDS, "limit": 1_000_000})["hits"]
    by_visitor: dict[str, list] = {}
    for h in hits:
        assert h.get("visitor_key"), f"a session without visitor_key: {h.get('day')} {h.get('session_key')}"
        by_visitor.setdefault(h["visitor_key"], []).append(h)
    run = uuid.uuid4().hex[:12]
    rows = [_visitor_row(sorted(s, key=lambda x: (x["day"], x["hour"], x["session_key"])), run)
            for s in by_visitor.values()]
    old = {r["pull_run"] for r in client.query(
        {"from": "web_visitors", "select": ["pull_run"], "limit": 1_000_000})["hits"]}
    for i in range(0, len(rows), UPLOAD_CHUNK):
        client.upload_batch("web_visitors", rows[i:i + UPLOAD_CHUNK])
    try:
        landed = client.query({"from": "web_visitors", "where": {"pull_run": run}, "limit": 0})["total"]
        assert landed == len(rows), f"web_visitors: {landed} of {len(rows)} rows landed"
        for previous in sorted(old - {run}):
            client.delete_entries("web_visitors", {"pull_run": previous})
    except Exception:
        client.delete_entries("web_visitors", {"pull_run": run})
        raise
    return {"visitors": len(rows), "sessions": len(hits), "pull_run": run,
            "replaced_runs": len(old)}


# ---- retention and deletion on request (docs/36, Antti 6.11.2026) ----

RETENTION_MONTHS = 13
# pull() reports that summarise the run rather than one day
RUN_REPORTS = {"retention", "web_visitors"}


def retention_cutoff(today: date) -> str:
    """The first day kept: `today` minus RETENTION_MONTHS calendar months,
    clamped to the month's last day (31.3. minus 13 months is 28.2.)."""
    import calendar
    months = today.year * 12 + today.month - 1 - RETENTION_MONTHS
    year, month = divmod(months, 12)
    month += 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).isoformat()


def prune_old_days(client: AitoClient, today: date) -> dict:
    """Delete web_sessions days before the retention cutoff and check none
    remain. web_visitors follows on the next rebuild."""
    cutoff = retention_cutoff(today)
    old = {"day": {"$lt": cutoff}}
    hits = client.query({"from": "web_sessions", "where": old, "select": ["day"],
                         "limit": 1_000_000})["hits"]
    # a v2 delete takes equality only, so each old day goes by its own value;
    # the steps go with their sessions
    for day in sorted({h["day"] for h in hits}):
        client.delete_entries("web_sessions", {"day": day})
        client.delete_entries("web_steps", {"day": day})
    left = client.query({"from": "web_sessions", "where": old, "limit": 0})["total"]
    assert left == 0, f"retention: {left} rows before {cutoff} survived the delete"
    return {"cutoff": cutoff, "pruned": len(hits)}


def forget_web_visitor(client: AitoClient, device_id: str | None = None,
                       visitor_key: str | None = None) -> dict:
    """Delete one browser on request: its web_sessions and web_visitors rows,
    and list its key in web_suppressed so later pulls skip it. Give the
    Amplitude device_id (the key is derived with the salt) or the visitor_key.
    Live tables only: backups expire on their own schedule (docs/36)."""
    assert (device_id is None) != (visitor_key is None), "give exactly one: device_id or visitor_key"
    key = visitor_key or _visitor_key(device_id)
    assert re.fullmatch(r"[0-9a-f]{16}", key), f"not a visitor key: {key!r}"
    where = {"visitor_key": key}
    counts = {t: client.query({"from": t, "where": where, "limit": 0})["total"]
              for t in ("web_sessions", "web_visitors", "web_steps", "web_suppressed")}
    for table in ("web_sessions", "web_visitors", "web_steps"):
        if counts[table]:
            client.delete_entries(table, where)
    if not counts["web_suppressed"]:
        client.upload_batch("web_suppressed", [{"visitor_key": key, "at": date.today().isoformat()}])
    left = {t: client.query({"from": t, "where": where, "limit": 0})["total"]
            for t in ("web_sessions", "web_visitors", "web_steps", "web_suppressed")}
    assert left == {"web_sessions": 0, "web_visitors": 0, "web_steps": 0, "web_suppressed": 1}, \
        f"forget {key}: left {left}"
    return {"visitor_key": key, "sessions_deleted": counts["web_sessions"],
            "visitors_deleted": counts["web_visitors"], "steps_deleted": counts["web_steps"],
            "suppressed": True}


# ---- web_steps: visits as linked steps (docs/37) ----

def _steps(client: AitoClient, rows: list[dict], run: str) -> list[dict]:
    """Pop each session row's `_steps` into web_steps rows: one per event,
    `prev` linking to the step before, the KPI the event's name belongs to,
    whether a later step of the same visit reaches each KPI, whether it is
    the exit, and the visit's arrival copied on (a link can't reach the rep1
    tables). Bots are not walked. Working out "later" and "exit" here is a
    fact about the visit, not a prediction (rule 2)."""
    platform = {p["post_id"]: p.get("platform") for p in client.query(
        {"from": "posts", "select": ["post_id", "platform"], "limit": 100000})["hits"]}
    out = []
    for r in rows:
        raw = r.pop("_steps")
        if r["likely_bot"]:
            continue
        key = r["session_key"]
        for n, (token, kpis) in enumerate(raw):
            later = {k for _, ks in raw[n + 1:] for k in ks}
            out.append({
                "step_id": f"{key}:{n}", "prev": f"{key}:{n - 1}" if n else None,
                "token": token, "n": n, "is_kpi": bool(kpis), "kpi": kpis[0] if kpis else None,
                **{f"kpi_after_{k}": k in later for k in KPI_EVENTS},
                "is_exit": n == len(raw) - 1,
                "source": r["source"], "utm_campaign": r.get("utm_campaign"),
                "referrer_domain": r.get("referrer_domain"),
                "post_platform": platform.get(r.get("post_id")), "post_id": r.get("post_id"),
                "visitor_key": r["visitor_key"], "day": r["day"], "pull_run": run,
            })
    return out


# ---- paths into a KPI, from the step graph (docs/37 phase 2) ----

PATH_DEPTH = ("prev.token", "prev.prev.token", "prev.prev.prev.token")


def web_paths_to(client: AitoClient, kpi: str, since: str | None = None,
                 until: str | None = None, platform: str | None = None) -> dict:
    """How visits reach one KPI, from web_steps and all in Aito (rule 2):
    - top_paths: Aito's $patterns over the prev chain into the KPI's steps
      (up to three steps back), each with the visits that took it, its lift,
      and the thin flag. These are Aito's top patterns, not a full count
      (paths of any length wait for aito-core's $walk, docs/37 gap 1);
    - raises_later: _relate of kpi_after_<kpi> over the step's token: the
      pages after which the visit more often goes on to reach the KPI;
    - drop_off: among visits that never reach it, _relate of is_exit over
      the token: where they end.
    `platform` keeps only visits that came from a post on that platform."""
    assert kpi in KPI_EVENTS, f"unknown kpi {kpi!r}; have {sorted(KPI_EVENTS)}"
    until = until or date.today().isoformat()
    since = since or (date.fromisoformat(until) - timedelta(days=29)).isoformat()
    clauses = [*_window(since, until), *([{"post_platform": platform}] if platform else [])]
    out = {"kpi": kpi, "since": since, "until": until, "platform": platform,
           "thin_below": WEB_THIN, "top_paths": [], "protective_paths": [],
           "raises_later": None, "drop_off": None}
    reached = client.query({"from": "web_steps", "where": {"$and": [*clauses, {"kpi": kpi}]},
                            "limit": 0})["total"]
    out["kpi_steps"] = reached
    if not reached:
        out["note"] = "no visit in the window reached it: nothing to walk"
        return out
    response = client.relate({"from": "web_steps", "where": {"$and": [*clauses, {"kpi": kpi}]},
                              "relate": {"$patterns": list(PATH_DEPTH)}, "limit": 10})
    hits = response.get("hits", [])
    shapes = []
    for hit in hits:
        props = (hit.get("related") or {}).get("$and") or [hit.get("related") or {}]
        shapes.append({k: v for p in props for k, v in p.items()})
    # thin is judged on distinct visits, never steps: one visitor reloading
    # must not make a row look solid (CPO, 6.11.2026)
    visits = _distinct_visits(client, [[*clauses, {"kpi": kpi}, *({k: v} for k, v in sh.items())]
                                       for sh in shapes])
    # $patterns mines over every step and scores against the KPI, so paths
    # never seen before it come back too, with a smoothed lift below 1
    # (documented; td-20261106110429784489): they lead nothing, but stay
    for hit, sh, n in zip(hits, shapes, visits):
        path = [sh[k] for k in reversed(PATH_DEPTH) if k in sh]
        into = (hit.get("lift") or 0) > 1
        row = {"path": path + ([_kpi_token(kpi)] if into else []), "visits": n,
               "support_overall": int(hit.get("f", 0)), "lift": hit.get("lift"),
               "thin": n < WEB_THIN}
        out["top_paths" if into else "protective_paths"].append(row)
    out["raises_later"] = _by_direction(client, relations.relate(
        client, "web_steps", {f"kpi_after_{kpi}": True},
        where={"is_kpi": False, "$and": clauses}, top_n=30, thin=WEB_THIN),
        [*clauses, {"is_kpi": False}])
    out["drop_off"] = _by_direction(client, relations.relate(
        client, "web_steps", {"is_exit": True},
        where={f"kpi_after_{kpi}": False, "is_kpi": False, "$and": clauses}, top_n=30, thin=WEB_THIN),
        [*clauses, {f"kpi_after_{kpi}": False}, {"is_kpi": False}])
    return out


def _distinct_visits(client: AitoClient, wheres: list[list[dict]]) -> list[int]:
    """For each step condition, how many distinct visits have such a step:
    the step ids are <session_key>:<n>, so the visit is the part before the
    last colon. One _batch round trip; counting is formatting (rule 2)."""
    if not wheres:
        return []
    answers = client.batch([{"from": "web_steps", "where": {"$and": w}, "select": ["step_id"],
                             "limit": 1_000_000} for w in wheres])
    return [len({h["step_id"].rsplit(":", 1)[0] for h in a.get("hits", [])}) for a in answers]


def _by_direction(client: AitoClient, rel: dict, population: list[dict]) -> dict:
    """Keep the token rows of a relate, judge thin on the distinct visits
    behind each, and split them: `relations` (lift > 1) lead, `protective`
    (lift <= 1) is kept apart, because the opposite direction is information
    too. Aito's own order is kept within each."""
    rows = [x for x in rel["relations"] if x["field"] == "token"]
    counts = _distinct_visits(client, [[*population, {"token": x["value"]}] for x in rows])
    for x, n in zip(rows, counts):
        x["visits"], x["thin"] = n, n < WEB_THIN
    return {**rel, "relations": [x for x in rows if x["lift"] > 1],
            "protective": [x for x in rows if x["lift"] <= 1]}


def _kpi_token(kpi: str) -> str:
    """How a path ends: the KPI's page when it is one page view, else its name."""
    tokens = sorted(_own_tokens(kpi))
    return tokens[0] if len(tokens) == 1 else f"kpi:{kpi}"


DIGEST_KINDS = ("raises_later", "drop_off")
# The digest's rolling window, computed weekly. At our volume a single week
# almost never gets past thin (the blog -> signup signal had 7 visits in 31
# days), so a signal is judged over the last four weeks (CPO, 6.11.2026).
DIGEST_WINDOW_DAYS = int(os.environ.get("COMPANY_AI_WEB_DIGEST_DAYS", "28"))


def web_digest(client: AitoClient, as_of: date | None = None) -> dict:
    """The weekly web digest (CPO, 6.11.2026): for every KPI, the step-graph
    signals of the DIGEST_WINDOW_DAYS before as_of that are not thin, read
    from web_paths_to's raises_later and drop_off: lift > 1 and at least
    WEB_THIN distinct visits. Computed weekly over a rolling window; a signal
    is `new` when last week's digest (the same window, seven days earlier) did
    not show it. Aito ranks and scores; nothing here is a threshold beyond
    thin (rule 2)."""
    as_of = as_of or date.today()
    span = lambda end: ((end - timedelta(days=DIGEST_WINDOW_DAYS)).isoformat(),
                        (end - timedelta(days=1)).isoformat())
    week, previous = span(as_of), span(as_of - timedelta(days=7))

    def solid(since: str, until: str) -> list[dict]:
        rows = []
        for kpi in KPI_EVENTS:
            r = web_paths_to(client, kpi=kpi, since=since, until=until)
            for kind in DIGEST_KINDS:
                for x in (r[kind] or {}).get("relations", []):
                    if not x["thin"]:
                        rows.append({"kpi": kpi, "kind": kind, "field": x["field"],
                                     "value": x["value"], "lift": x["lift"], "visits": x["visits"]})
        return rows

    before = {(s["kpi"], s["kind"], s["value"]) for s in solid(*previous)}
    signals = [{**s, "new": (s["kpi"], s["kind"], s["value"]) not in before}
               for s in solid(*week)]
    return {"week": f"{week[0]}..{week[1]}", "previous": f"{previous[0]}..{previous[1]}",
            "window_days": DIGEST_WINDOW_DAYS, "thin_below": WEB_THIN, "signals": signals}


_DIGEST_LABELS = {"raises_later": "raises it later in the visit",
                  "drop_off": "visits that never reach it end here"}


def digest_document(digest: dict) -> tuple[str, str]:
    """The digest as a (title, body) document, for the Monday pull to save
    (area marketing, topics web;digest). Formatting only."""
    title = f"Web digest, {digest['week']}"
    lines = [f"Signals with at least {digest['thin_below']} distinct visits over the "
             f"{digest['window_days']} days {digest['week']}, from Aito's _relate over the step "
             f"graph (web_paths_to). NEW: not shown last week ({digest['previous']})."]
    if not digest["signals"]:
        lines.append("")
        lines.append("No signal cleared the thin threshold this week.")
    for kpi in KPI_EVENTS:
        rows = [s for s in digest["signals"] if s["kpi"] == kpi]
        if rows:
            lines += ["", f"{kpi}:"]
            lines += [f"- {s['value']}: {_DIGEST_LABELS[s['kind']]}, {s['lift']:.2f}× over "
                      f"{s['visits']} visits{' (NEW)' if s['new'] else ''}" for s in rows]
    return title, "\n".join(lines)
