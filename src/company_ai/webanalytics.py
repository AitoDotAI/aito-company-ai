"""aito.ai web analytics: Amplitude page views as web_sessions rows (docs/35).

One UTC day of Amplitude's Export API becomes one row per session. The export
holds raw user ids, device ids, IPs and full URLs; none of it is kept. Rows
are built field by field (an allow-list), paths are cut at `?`/`#`, and the
session key is a hash of the session's own ids. The export is parsed in
memory and never written to disk.

Classification here (source from utm_medium/referrer, device class from the
OS, probe paths) is a fixed label lookup, not a score. Every prediction is an
Aito query (rule 2): `predict_next_path`, and `relate` over the table.
"""

import gzip
import hashlib
import io
import json
import os
import zipfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import requests

from . import relations, schema
from .aito import AitoClient

EXPORT_URL = "https://analytics.eu.amplitude.com/api/2/export"
SITE_HOST = "aito.ai"
LOOKBACK_DAYS = 3   # referrer_day: a post on the referrer's platform this many days before

# the two page-view shapes the site sends (docs/35)
PAGE_VIEW_PREFIXES = {"Page View": "Page View: ", "Viewed": "Viewed"}
CTA_SUFFIX = "_cta_clicked"
SIGNUP_PATHS = ("/signup", "/sign-up", "/register")

PROBE_PREFIXES = ("/wp-", "/wordpress", "/xmlrpc.php", "/.env", "/.git", "/admin",
                  "/phpmyadmin", "/airdrops", "/cgi-bin", "/vendor/", "/.well-known/security.txt",
                  "/account/login", "/auth/", "/app", "/config")

SEARCH_HOSTS = ("google.", "bing.com", "duckduckgo.com", "yahoo.", "ecosia.org", "yandex.",
                "baidu.com", "search.brave.com", "startpage.com")
SOCIAL_HOSTS = {"linkedin.com": "linkedin", "lnkd.in": "linkedin",
                "news.ycombinator.com": "hackernews", "reddit.com": "reddit",
                "old.reddit.com": "reddit", "x.com": None, "twitter.com": None, "t.co": None,
                "facebook.com": None, "bsky.app": None, "mastodon.social": None}
MEDIUM_SOURCES = {"social": "social", "email": "email", "newsletter": "email",
                  "cpc": "paid", "ppc": "paid", "paid": "paid", "paid_social": "paid",
                  "referral": "referral", "organic": "organic"}
OS_DEVICES = {"ios": "mobile", "android": "mobile", "ipados": "tablet",
              "windows": "desktop", "mac os x": "desktop", "macos": "desktop",
              "linux": "desktop", "chrome os": "desktop", "ubuntu": "desktop"}


def _strip_query(url: str) -> str:
    """The URL or path cut at its query string and fragment."""
    return url.split("#", 1)[0].split("?", 1)[0]


def _session_key(session_id, device_id) -> str:
    return hashlib.sha256(f"{session_id}:{device_id}".encode()).hexdigest()[:16]


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


def _page(event: dict) -> str:
    """The page an event viewed, query and fragment dropped, other hosts
    host-first."""
    props = event.get("event_properties") or {}
    path = props.get("[Amplitude] Page Path") or props.get("path")
    if path is None and event["event_type"].startswith("Page View: "):
        path = event["event_type"][len("Page View: "):]
    assert path, f"a page view without a path: {event['event_type']!r} {sorted(props)}"
    path = _strip_query(path)
    host = (props.get("[Amplitude] Page Domain") or SITE_HOST).lower()
    host = host[4:] if host.startswith("www.") else host
    return path if host == SITE_HOST else f"{host}{path}"


def _device_class(os_name: str | None) -> str:
    return OS_DEVICES.get((os_name or "").lower(), "unknown")


def _source(medium: str | None, referrer: str | None) -> str:
    if medium:
        return MEDIUM_SOURCES.get(medium.lower(), "other")
    if not referrer or referrer == SITE_HOST or referrer.endswith("." + SITE_HOST):
        return "direct"
    if any(referrer.startswith(h) or ("." + h) in referrer for h in SEARCH_HOSTS):
        return "organic"
    if referrer in SOCIAL_HOSTS:
        return "social"
    return "referral"


def _time(event: dict) -> datetime:
    return datetime.fromisoformat(event["event_time"][:19])


def sessions_from_events(events: list[dict], day: str) -> list[dict]:
    """One row per session that has a page view, built field by field. Links
    to posts and experiments are filled in by `store_day`."""
    by_session: dict = {}
    for event in events:
        key = (event.get("session_id"), event.get("device_id"))
        by_session.setdefault(key, []).append(event)
    rows = []
    for (session_id, device_id), group in by_session.items():
        group.sort(key=_time)
        views = [e for e in group if _page_kind(e)]
        if not views:
            continue
        first = views[0]
        props = first.get("event_properties") or {}
        url = props.get("[Amplitude] Page URL") or ""
        query = parse_qs(urlsplit(url).query)
        utm = {k: (query.get(k) or [None])[0] for k in ("utm_source", "utm_medium", "utm_campaign")}
        referrer = _host(props.get("referrer"))
        pages = [_page(e) for e in views]
        ctas = [e for e in group if e["event_type"].endswith(CTA_SUFFIX)]
        start = _time(group[0])
        rows.append({
            "session_key": _session_key(session_id, device_id),
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
            "source": _source(utm["utm_medium"], referrer),
            **utm,
            "device_class": _device_class(first.get("os_name")),
            "country": first.get("country") or "unknown",
            "likely_bot": pages[0].startswith(PROBE_PREFIXES),
            "post_id": None, "experiment_id": None, "link_basis": None,
        })
    return rows


def _link(client: AitoClient, rows: list[dict], day: str) -> None:
    """Fill post_id/experiment_id/link_basis: exact by utm_campaign, else a
    referrer_day candidate (exactly one post on the referrer's platform in the
    LOOKBACK_DAYS before)."""
    posts = client.query({"from": "posts", "limit": 100000,
                          "select": ["post_id", "platform", "status", "posted_at", "utm_campaign"]})["hits"]
    by_campaign = {p["utm_campaign"]: p["post_id"] for p in posts if p.get("utm_campaign")}
    experiments = {e["experiment_id"] for e in client.query(
        {"from": "experiments", "limit": 100000, "select": ["experiment_id"]})["hits"]}
    end = date.fromisoformat(day)
    start = (end - timedelta(days=LOOKBACK_DAYS)).isoformat()
    for row in rows:
        if row["likely_bot"]:
            continue
        campaign = row["utm_campaign"]
        if campaign and (campaign in by_campaign or campaign in experiments):
            row["post_id"] = by_campaign.get(campaign)
            row["experiment_id"] = campaign if campaign in experiments else None
            row["link_basis"] = "utm_campaign"
            continue
        platform = SOCIAL_HOSTS.get(row["referrer_domain"] or "")
        if not platform:
            continue
        near = [p for p in posts if p.get("platform") == platform and p.get("status") == "posted"
                and start <= (p.get("posted_at") or "")[:10] <= day]
        if len(near) == 1:
            row["post_id"], row["link_basis"] = near[0]["post_id"], "referrer_day"


def _report(events: list[dict], rows: list[dict]) -> dict:
    mapped, unmapped = Counter(), Counter()
    for e in events:
        kind = _page_kind(e)
        if kind:
            mapped[kind] += 1
        elif not e["event_type"].endswith(CTA_SUFFIX):
            unmapped[e["event_type"]] += 1
    unknown_os = Counter()
    first_os = {}
    for e in sorted(events, key=_time):
        first_os.setdefault(_session_key(e.get("session_id"), e.get("device_id")), e.get("os_name"))
    for r in rows:
        if r["device_class"] == "unknown":
            unknown_os[str(first_os.get(r["session_key"]))] += 1
    return {"events": len(events), "sessions": len(rows),
            "bots": sum(r["likely_bot"] for r in rows),
            "linked": Counter(r["link_basis"] for r in rows if r["link_basis"]),
            "mapped": dict(mapped), "unmapped": dict(unmapped), "unknown_os": dict(unknown_os),
            # a page on another host is written host-first, not starting with "/"
            "multi_host_sessions": sum(any(not p.startswith("/") for p in r["pages"].split())
                                       for r in rows)}


def store_day(client: AitoClient, day: str, events: list[dict]) -> dict:
    """Replace `day`'s web_sessions rows with the sessions in `events`.
    Re-running a day gives the same rows. Returns the run's report."""
    date.fromisoformat(day)
    rows = sessions_from_events(events, day)
    _link(client, rows, day)
    for r in rows:
        assert r["source"] in schema.WEB_SOURCES and r["device_class"] in schema.DEVICE_CLASSES, r
    client.delete_entries("web_sessions", {"day": day})
    if rows:
        client.upload_batch("web_sessions", rows)
    stored = client.query({"from": "web_sessions", "where": {"day": day}, "limit": 0})["total"]
    assert stored == len(rows), f"web_sessions {day}: stored {stored}, built {len(rows)}"
    report = _report(events, rows)
    report["linked"] = dict(report["linked"])
    return {"day": day, **report}


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


def fetch_day(day: str) -> list[dict]:
    """One UTC day from the Export API. The keys come from the environment
    (AMPLITUDE_API_KEY, AMPLITUDE_SECRET_KEY), placed by the operator; they
    are used for the request and never logged. No data for the day is an
    empty list (Amplitude answers 404)."""
    key, secret = os.environ.get("AMPLITUDE_API_KEY"), os.environ.get("AMPLITUDE_SECRET_KEY")
    assert key and secret, "AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY are not set (docs/35)"
    stamp = day.replace("-", "")
    response = requests.get(EXPORT_URL, params={"start": f"{stamp}T00", "end": f"{stamp}T23"},
                            auth=(key, secret), timeout=300)
    if response.status_code == 404:
        return []
    assert response.status_code == 200, \
        f"Amplitude export {day}: HTTP {response.status_code} {response.text[:200]}"
    return events_from_export(response.content)


def pull(client: AitoClient, days: int = LOOKBACK_DAYS, day: str | None = None) -> list[dict]:
    """Pull `day`, or the last `days` complete UTC days, into web_sessions."""
    if day:
        wanted = [day]
    else:
        today = datetime.now(timezone.utc).date()
        wanted = [(today - timedelta(days=n)).isoformat() for n in range(days, 0, -1)]
    return [store_day(client, d, fetch_day(d)) for d in wanted]


def _top(counts: Counter, n: int = 10) -> list:
    """The n most frequent values, ties in value order."""
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def _rows(client: AitoClient, since: str, until: str, select: list[str], where: dict | None = None):
    clauses = [{"day": {"$gte": since}}, {"day": {"$lte": until}}, *(
        {k: v} for k, v in (where or {}).items() if v is not None)]
    return client.query({"from": "web_sessions", "where": {"$and": clauses},
                         "select": select, "limit": 100000})["hits"]


def web_traffic(client: AitoClient, since: str, until: str, path: str | None = None,
                campaign: str | None = None, source: str | None = None) -> dict:
    """Per-day sessions, views, onward clicks and sign-up CTAs (bots counted
    apart), the top landing pages and sources, and the posts the visits link to."""
    rows = _rows(client, since, until, ["day", "views", "onward_click", "signup_cta", "likely_bot",
                                         "landing_path", "source", "post_id", "link_basis"],
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
    links = Counter((r["post_id"], r["link_basis"]) for r in human if r.get("post_id"))
    links = sorted(links.items(), key=lambda kv: (-kv[1], kv[0]))
    return {"since": since, "until": until, "days": [days[d] for d in sorted(days)],
            "bots": len(rows) - len(human),
            "top_landing": _top(Counter(r["landing_path"] for r in human)),
            "top_sources": _top(Counter(r["source"] for r in human)),
            "posts": [{"post_id": p, "link_basis": b, "sessions": n} for (p, b), n in links]}


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


def onward_drivers(client: AitoClient, top_n: int = 10) -> dict:
    """Which source, landing page, device and campaign go with an onward
    click: Aito's _relate over human sessions."""
    return relations.relate(client, "web_sessions", {"onward_click": True},
                            where={"likely_bot": False}, top_n=top_n)
