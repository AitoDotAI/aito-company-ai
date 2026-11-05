"""aito.ai web analytics: an Amplitude export lands as web_sessions rows.

The pull (docs/35) turns one UTC day of raw Amplitude events into one row per
session: landing and next path, views, onward click, source and campaign,
device class, a bot flag, and a link to the post or experiment that brought
the visit. The fixture (data/fixtures/amplitude_export_2026-10-05.jsonl) is
invented, in the export's shape: both page-view shapes ("Page View: /path" and
"Viewed …"), a CTA, a demo page on another host, a probe, an unknown OS, and
raw user ids, device ids, IPs and query strings that must not be stored.

These books assert the stored values, not a row count, and show that the
privacy check fails when the scrubbing is stubbed out.
"""

import gzip
import io
import json
import zipfile
from datetime import date
from pathlib import Path

import booktest as bt

from company_ai import engagements, loaders, log, webanalytics
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "amplitude_export_2026-10-05.jsonl"
DAY = "2026-10-05"


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key, 120)


def _events() -> list[dict]:
    return [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]


def _seeded() -> AitoClient:
    """Seed posts and experiments, tag one post with the fixture's campaign
    slug, and post one on Hacker News two days before the fixture's day."""
    client = _client()
    loaders.create_schema(client)
    for load in (loaders.load_materials, loaders.load_channels, loaders.load_posts,
                 loaders.load_experiments):
        load(client, SEED_DIR)
    client.delete_table("web_sessions")
    loaders.create_schema(client)
    material = client.query({"from": "materials", "limit": 1})["hits"][0]["material_id"]
    li = log.add_post(client, material_id=material, channel_id="sk04", tone="narrate",
                      format="link", link_placement="body", utm_campaign="ecom-screen")
    log.log_post_result(client, li["post_id"], outcome="modest", reach_or_views=900,
                        posted_at="2026-10-03")
    hn = log.add_post(client, material_id=material, channel_id="sk01", tone="builder",
                      format="show-hn", link_placement="n_a")
    log.log_post_result(client, hn["post_id"], outcome="win", reach_or_views=5000,
                        posted_at="2026-10-03")
    return client, li["post_id"], hn["post_id"]


def _clean(client: AitoClient) -> None:
    """Leave the shared test env without web rows, so other books' table
    listings (test_migrate's doctor) don't depend on run order."""
    client.delete_entries("web_sessions", {"day": DAY})


def _masked(value, names: dict) -> str:
    """JSON with the generated post ids replaced by stable names."""
    text = json.dumps(value, sort_keys=True, indent=None if not isinstance(value, dict) or
                      "days" not in value else 1)
    for post_id, name in names.items():
        text = text.replace(post_id, name)
    return text


def _rows(client: AitoClient) -> dict:
    hits = client.query({"from": "web_sessions", "where": {"day": DAY}, "limit": 1000})["hits"]
    rows = {r["country"]: r for r in hits}    # the fixture's sessions differ by country
    assert len(rows) == len(hits), f"two sessions share a country: {hits}"
    return rows


SECRETS = ["visitor-alice-7f3", "visitor-bob-2c9", "dev-0a1b2c3d",
           "dev-4e5f6a7b", "dev-8c9d0e1f", "dev-2a3b4c5d", "dev-6e7f8a9b",
           "203.0.113.7", "198.51.100.23", "192.0.2.66", "203.0.113.99", "198.51.100.200",
           "1759658400000", "fbclid", "XYZ123", "redirect_to", "ref=abc"]
PATH_FIELDS = ("landing_path", "next_path", "pages")


def _leaks(rows) -> list[str]:
    """Every raw identifier or query-string trace found in any stored field."""
    found = []
    for row in rows:
        for field, value in row.items():
            text = json.dumps(value)
            found += [f"{field}: {s}" for s in SECRETS if s in text]
            if field in PATH_FIELDS and value and any(c in str(value) for c in "?=#"):
                found.append(f"{field}: query/fragment in {value!r}")
            if field in PATH_FIELDS and value and "utm_" in str(value):
                found.append(f"{field}: utm in {value!r}")
    return found


def test_a_day_lands_as_session_rows(t: bt.TestCaseRun) -> None:
    client, li_post, hn_post = _seeded()
    t.h1("Store one day from the fixture")
    report = webanalytics.store_day(client, DAY, _events())
    t.tln(json.dumps(report, sort_keys=True, indent=1))
    assert report["mapped"] == {"Page View": 8, "Viewed": 2}, report["mapped"]
    assert report["unmapped"] == {"Instance create": 1}, report["unmapped"]
    assert report["unknown_os"] == {"PlayStation": 1}, report["unknown_os"]

    rows = _rows(client)
    t.h1("Stored rows")
    names = {li_post: "<li-post>", hn_post: "<hn-post>"}
    for country in sorted(rows):
        t.tln(_masked({k: v for k, v in rows[country].items() if k != "session_key"}, names))

    li = rows["Finland"]
    t.h1("The LinkedIn session")
    expected = {"next_path": "/pricing/", "pages": "/blog/every-screen-a-decision/ /pricing/ /signup/",
                "views": 3, "engaged_seconds": 270, "onward_click": True, "signup_cta": True,
                "referrer_domain": "linkedin.com", "source": "social", "utm_source": "linkedin",
                "utm_medium": "social", "utm_campaign": "ecom-screen", "device_class": "mobile",
                "country": "Finland", "likely_bot": False, "post_id": li_post,
                "link_basis": "utm_campaign", "hour": 10, "weekday": "mon", "week": "2026-W41"}
    wrong = {k: (v, li.get(k)) for k, v in expected.items() if li.get(k) != v}
    t.tln(f"wrong: {wrong}")
    assert not wrong, wrong

    t.h1("The Hacker News bounce: a candidate link, not a bot")
    hn = rows["United States"]
    t.tln(_masked({k: hn.get(k) for k in ("views", "onward_click", "likely_bot", "source",
                                          "post_id", "link_basis")}, names))
    assert (hn["landing_path"], hn["referrer_domain"]) == ("/", "news.ycombinator.com")
    assert (hn["views"], hn["onward_click"], hn["likely_bot"]) == (1, False, False)
    assert (hn.get("post_id"), hn.get("link_basis")) == (hn_post, "referrer_day")

    t.h1("The probe is flagged, kept")
    bot = rows["Netherlands"]
    assert bot["landing_path"] == "/wp-login.php"
    assert bot["likely_bot"] is True and bot.get("post_id") is None

    t.h1("The direct visit: Viewed shape, a CTA, a demo page on another host")
    direct = rows["Germany"]
    t.tln(json.dumps({k: direct.get(k) for k in ("landing_path", "next_path", "pages", "views",
                                                 "onward_click", "signup_cta", "source")},
                     sort_keys=True))
    assert (direct["landing_path"], direct["next_path"]) == ("/", "ecommerce.aito.ai/cart")
    assert (direct["views"], direct["onward_click"], direct["signup_cta"], direct["source"]) == \
        (2, True, True, "direct")

    t.h1("The search visit: repeats kept in order, unknown device")
    docs = rows["Sweden"]
    assert docs["pages"] == "/docs/ /docs/api/v2/quickstart/ /docs/", docs["pages"]
    assert (docs["source"], docs["device_class"], docs["views"]) == ("organic", "unknown", 3)

    t.h1("Nothing raw is stored")
    leaks = _leaks(rows.values())
    t.tln(f"leaks: {leaks}")
    assert not leaks, leaks
    _clean(client)


def test_the_privacy_check_fails_without_the_scrubbing(t: bt.TestCaseRun) -> None:
    t.h1("Sessions built with the path scrubber and the key hash stubbed out")
    strip, key = webanalytics._strip_query, webanalytics._session_key
    try:
        webanalytics._strip_query = lambda url: url
        webanalytics._session_key = lambda session_id, device_id: f"{session_id}:{device_id}"
        rows = webanalytics.sessions_from_events(_events(), DAY)
    finally:
        webanalytics._strip_query, webanalytics._session_key = strip, key
    leaks = _leaks(rows)
    for leak in sorted(set(leaks)):
        t.tln(leak)
    assert leaks, "the privacy check found nothing with the scrubbing off: it is not live"


def test_a_repull_replaces_the_day(t: bt.TestCaseRun) -> None:
    client, _, _ = _seeded()
    webanalytics.store_day(client, DAY, _events())
    first = _rows(client)
    webanalytics.store_day(client, DAY, _events())
    second = _rows(client)
    t.h1("Stored twice")
    t.tln(f"{len(first)} rows, then {len(second)}")
    assert first == second, "a re-pull changed the stored rows"
    _clean(client)


def test_the_export_is_parsed_in_memory(t: bt.TestCaseRun) -> None:
    t.h1("An export zip of gzipped JSON lines, read without touching disk")
    raw = FIXTURE.read_bytes()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("100040781/100040781_2026-10-05_0#0.json.gz", gzip.compress(raw))
    events = webanalytics.events_from_export(buffer.getvalue())
    t.tln(f"{len(events)} events; first {events[0]['event_type']!r}")
    assert events == _events()


def test_reads_and_the_dogfood_queries(t: bt.TestCaseRun) -> None:
    client, li_post, hn_post = _seeded()
    webanalytics.store_day(client, DAY, _events())
    t.h1("web_traffic for the day (bots excluded)")
    traffic = webanalytics.web_traffic(client, since=DAY, until=DAY)
    t.tln(_masked(traffic, {li_post: "<li-post>", hn_post: "<hn-post>"}))
    assert traffic["days"] == [{"day": DAY, "sessions": 4, "views": 9, "onward_clicks": 3,
                                "signup_ctas": 2}], traffic["days"]
    assert traffic["bots"] == 1

    t.h1("web_paths: landing -> next, by source and device")
    paths = webanalytics.web_paths(client, since=DAY, until=DAY)
    t.tln(json.dumps(paths, sort_keys=True, indent=1))
    assert {"week": "2026-W41", "landing_path": "/blog/every-screen-a-decision/",
            "next_path": "/pricing/", "source": "social", "device_class": "mobile",
            "sessions": 1} in paths["paths"]

    t.h1("The weekly KPIs carry the web line")
    # as_of a Wednesday: weekly() leaves the current week out when as_of is a
    # Monday (td-20261105090816359072, pre-existing), so the book picks W41 by name
    weeks = engagements.weekly(client, as_of=date(2026, 10, 7), weeks=1)["weeks"]
    week = next(w for w in weeks if w["week"] == "2026-W41")
    t.tln(json.dumps({k: week[k] for k in ("week", "web_sessions", "web_onward_click_rate")},
                     sort_keys=True))
    assert (week["week"], week["web_sessions"], week["web_onward_click_rate"]) == \
        ("2026-W41", 4, 0.75), week

    t.h1("A campaign slug is unique across posts")
    material = client.query({"from": "materials", "limit": 1})["hits"][0]["material_id"]
    for slug in ("ecom-screen", "Ecom Screen"):
        try:
            log.add_post(client, material_id=material, channel_id="sk04", tone="narrate",
                         format="link", link_placement="body", utm_campaign=slug)
            raise RuntimeError(f"accepted utm_campaign {slug!r}")
        except AssertionError as e:
            t.tln(f"{slug!r}: {str(e).split(' is already post')[0]}")

    t.h1("Dogfood: the next page, predicted from how the visitor arrived")
    request, response = webanalytics.predict_next_path(
        client, landing_path="/blog/every-screen-a-decision/", source="social",
        device_class="mobile")
    t.tln(f"request:  {json.dumps(request, sort_keys=True)}")
    t.tln(f"response: {json.dumps(response, sort_keys=True)[:600]}")
    assert request["predict"] == "next_path" and request["from"] == "web_sessions"
    _clean(client)
