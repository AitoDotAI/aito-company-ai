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

# the two page-view shapes the site sends (docs/35)
PAGE_VIEW_PREFIXES = {"Page View": "Page View: ", "Viewed": "Viewed"}
CTA_SUFFIX = "_cta_clicked"
SIGNUP_PATHS = ("/signup", "/sign-up", "/register")
NO_SESSION = (-1, None)   # Amplitude's "no session": each such event stands alone

# the context a visitor arrives with: what onward clicks may be related to
PRE_VISIT = ("source", "referrer_domain", "utm_source", "utm_medium", "utm_campaign",
             "landing_path", "device_class", "country", "weekday", "hour")

PROBE_PREFIXES = ("/wp-", "/wordpress", "/xmlrpc.php", "/.env", "/.git", "/admin",
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


def _session_key(session_id, device_id) -> str:
    return hashlib.sha256(f"{session_id}:{device_id}".encode()).hexdigest()[:16]


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
                if not e["event_type"].endswith(CTA_SUFFIX):
                    stats["unmapped"][e["event_type"]] += 1
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
        rows.append({
            "session_key": _session_key(*key[:2]) if key[0] not in NO_SESSION
            else _session_key(key[0], f"{key[1]}:{key[2]}"),
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
            "likely_bot": pages[0].startswith(PROBE_PREFIXES),
            "post_id": None, "candidate_post_id": None, "experiment_id": None,
            "link_basis": None,
        })
    return rows, stats


def sessions_from_events(events: list[dict], day: str) -> list[dict]:
    """One row per session that started on `day` and has a page view, built
    field by field. Links are filled in by `store_day`."""
    return _build(events, day)[0]


def _link(client: AitoClient, rows: list[dict], day: str) -> dict:
    """Fill the links. Exact: utm_campaign is one post's slug (post_id) or an
    experiment_id. Candidate: exactly one post on the referrer's platform in
    the LOOKBACK_DAYS before (candidate_post_id). A visit before the post went
    out is never credited; a slug two posts share links nothing. Returns what
    was refused, by kind."""
    posts = client.query({"from": "posts", "limit": 100000,
                          "select": ["post_id", "platform", "status", "posted_at", "utm_campaign"]})["hits"]
    by_campaign: dict[str, list[dict]] = {}
    for p in posts:
        if p.get("utm_campaign"):
            by_campaign.setdefault(p["utm_campaign"], []).append(p)
    experiments = {e["experiment_id"] for e in client.query(
        {"from": "experiments", "limit": 100000, "select": ["experiment_id"]})["hits"]}
    duplicates = {slug: sorted(p["post_id"] for p in ps)
                  for slug, ps in by_campaign.items() if len(ps) > 1}
    start = (date.fromisoformat(day) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    before_post = 0
    for row in rows:
        if row["likely_bot"]:
            continue
        campaign = row["utm_campaign"]
        if campaign and campaign in by_campaign and campaign not in duplicates:
            post = by_campaign[campaign][0]
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
        near = [p for p in posts if p.get("platform") == platform and p.get("status") == "posted"
                and start <= (p.get("posted_at") or "")[:10] <= day]
        if len(near) == 1:
            row["candidate_post_id"], row["link_basis"] = near[0]["post_id"], "referrer_day"
    return {"duplicate_campaigns": duplicates, "before_post": before_post}


def store_day(client: AitoClient, day: str, events: list[dict]) -> dict:
    """Make `day`'s web_sessions rows the sessions in `events` that started
    on it. The new rows are uploaded under a fresh pull_run and checked
    before the old runs' rows are deleted, so a failed upload leaves the day
    as it was. A day with no sessions keeps any rows it had and is flagged
    empty. Returns the run's report."""
    date.fromisoformat(day)
    rows, stats = _build(events, day)
    refused = _link(client, rows, day)
    run = uuid.uuid4().hex[:12]
    for r in rows:
        assert r["source"] in schema.WEB_SESSION_SOURCES and r["device_class"] in schema.DEVICE_CLASSES, r
        r["pull_run"] = run
    old = {r.get("pull_run") for r in client.query(
        {"from": "web_sessions", "where": {"day": day}, "select": ["pull_run"], "limit": 100000})["hits"]}
    kept = 0
    if rows:
        client.upload_batch("web_sessions", rows)
        try:
            landed = client.query({"from": "web_sessions", "where": {"day": day, "pull_run": run},
                                   "limit": 0})["total"]
            assert landed == len(rows), f"web_sessions {day}: {landed} of {len(rows)} rows landed"
            for previous in sorted(p for p in old if p):
                client.delete_entries("web_sessions", {"day": day, "pull_run": previous})
        except Exception:
            # the old rows stay the day's rows; the new run must not double it
            client.delete_entries("web_sessions", {"day": day, "pull_run": run})
            raise
    else:
        kept = client.query({"from": "web_sessions", "where": {"day": day}, "limit": 0})["total"]
    linked = Counter(r["link_basis"] for r in rows if r["link_basis"])
    return {"day": day, "pull_run": run, "events": len(events), "sessions": len(rows),
            "empty": not rows, "kept_previous": kept,
            "bots": sum(r["likely_bot"] for r in rows), "linked": dict(linked),
            "mapped": dict(stats["mapped"]), "unmapped": dict(stats["unmapped"]),
            "unknown_os": dict(stats["unknown_os"]),
            "no_session_events": stats["no_session_events"],
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
                                         "landing_path", "source", "post_id", "candidate_post_id"],
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
                                             if r.get("candidate_post_id")), 50)]}


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

WEB_VIEW_FIELDS = ["day", "hour", "landing_path", "next_path", "source", "referrer_domain",
                   "utm_campaign", "post_id", "device_class", "country", "views",
                   "engaged_seconds", "onward_click", "signup_cta", "likely_bot"]


def web_view(client: AitoClient, since: str, until: str, source: str | None = None,
             campaign: str | None = None, path: str | None = None, device: str | None = None,
             limit: int = 25, offset: int = 0) -> dict:
    """What the Web view shows for one filter.
    - totals and the per-day series: counts over the matching human sessions;
    - facets: the filter choices, from the whole window, so a chosen filter
      doesn't hide the alternatives;
    - drivers: Aito's _relate of onward_click over the same population;
    - next_paths: Aito's _predict next_path when a landing page is chosen;
    - sessions: a page of the matching rows, newest first, bots included and
      flagged.
    Counting and paging are formatting; every relation and prediction is Aito's
    (rule 2)."""
    filt = {"source": source, "utm_campaign": campaign, "landing_path": path,
            "device_class": device}
    rows = _rows(client, since, until, WEB_VIEW_FIELDS, filt)
    human = [r for r in rows if not r["likely_bot"]]
    days: dict = {}
    for r in human:
        d = days.setdefault(r["day"], {"day": r["day"], "sessions": 0, "onward_clicks": 0,
                                       "signup_ctas": 0})
        d["sessions"] += 1
        d["onward_clicks"] += r["onward_click"]
        d["signup_ctas"] += r["signup_cta"]
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
    drivers = relations.relate(client, "web_sessions", {"onward_click": True},
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
            "drivers": drivers, "next_paths": next_paths,
            "session_total": len(rows), "sessions": ordered[offset:offset + limit]}
