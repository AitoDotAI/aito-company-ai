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
import os
import re
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import booktest as bt

from company_ai import engagements, loaders, log, schema, webanalytics
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


TOKEN = re.compile(r"[0-9a-f]{16,}|[A-Za-z0-9_]{24,}")
# the generated ids the table is allowed to hold (session_key is the 16-hex hash)
ID_FIELDS = {"session_key", "post_id", "candidate_post_id", "experiment_id", "pull_run"}


def _leaks(rows) -> list[str]:
    """Every raw identifier, query-string trace, email or long token found in
    any stored field but the generated ids (ID_FIELDS)."""
    found = []
    for row in rows:
        for field, value in row.items():
            text = json.dumps(value)
            found += [f"{field}: {s}" for s in SECRETS if s in text]
            if "@" in text or "%40" in text.lower():
                found.append(f"{field}: email-shaped {value!r}")
            if field not in ID_FIELDS and TOKEN.search(text):
                found.append(f"{field}: long token in {value!r}")
            if field in PATH_FIELDS and value and any(c in str(value) for c in "?=#"):
                found.append(f"{field}: query/fragment in {value!r}")
            if field in PATH_FIELDS and value and "utm_" in str(value):
                found.append(f"{field}: utm in {value!r}")
    return found


def test_a_day_lands_as_session_rows(t: bt.TestCaseRun) -> None:
    client, li_post, hn_post = _seeded()
    t.h1("Store one day from the fixture")
    report = webanalytics.store_day(client, DAY, _events())
    t.tln(json.dumps({k: v for k, v in report.items() if k != "pull_run"}, sort_keys=True, indent=1))
    assert report["mapped"] == {"Page View": 8, "Viewed": 2}, report["mapped"]
    assert report["unmapped"] == {"Instance create": 1}, report["unmapped"]
    assert report["unknown_os"] == {"PlayStation": 1}, report["unknown_os"]
    assert (report["utm_present"], report["referrer_present"]) == (1, 3), report

    rows = _rows(client)
    t.h1("Stored rows")
    names = {li_post: "<li-post>", hn_post: "<hn-post>"}
    for country in sorted(rows):
        t.tln(_masked({k: v for k, v in rows[country].items()
                       if k not in ("session_key", "pull_run")}, names))

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
                                          "post_id", "candidate_post_id", "link_basis")}, names))
    assert (hn["landing_path"], hn["referrer_domain"]) == ("/", "news.ycombinator.com")
    assert (hn["views"], hn["onward_click"], hn["likely_bot"]) == (1, False, False)
    assert (hn.get("post_id"), hn.get("candidate_post_id"), hn.get("link_basis")) == \
        (None, hn_post, "referrer_day")

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
    def without_run(rows):
        return {k: {f: v for f, v in r.items() if f != "pull_run"} for k, r in rows.items()}
    first = without_run(_rows(client))
    webanalytics.store_day(client, DAY, _events())
    second = without_run(_rows(client))
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


def _event(when: str, path: str, session_id, device_id="dev-midnight", **props) -> dict:
    """One page view, in the export's shape, at `when` (YYYY-MM-DD HH:MM:SS UTC)."""
    url = props.pop("url", f"https://aito.ai{path}")
    return {"$insert_id": f"ins-{session_id}-{when}-{path}", "event_type": f"Page View: {path}",
            "event_time": f"{when}.000000", "session_id": session_id, "device_id": device_id,
            "user_id": None, "ip_address": "198.51.100.77", "os_name": "Windows",
            "country": "Finland", "platform": "Web",
            "event_properties": {"[Amplitude] Page Path": path, "[Amplitude] Page Domain": "aito.ai",
                                 "[Amplitude] Page URL": url, **props},
            "user_properties": {}}


def test_onward_drivers_use_only_pre_visit_context(t: bt.TestCaseRun) -> None:
    client, _, _ = _seeded()
    webanalytics.store_day(client, DAY, _events())
    t.h1("relate on onward_click: the fields left as drivers")
    result = webanalytics.onward_drivers(client, since=DAY, until=DAY)
    columns = set(schema.WEB_SESSIONS["columns"])
    drivers = sorted(columns - set(result["excluded"]))
    t.tln(f"drivers: {drivers}")
    t.tln(f"where: {json.dumps(result['where'], sort_keys=True)}")
    assert drivers == sorted(webanalytics.PRE_VISIT), \
        f"onward_click is explained by {sorted(set(drivers) - set(webanalytics.PRE_VISIT))}"
    _clean(client)


def test_a_session_crossing_midnight_is_one_row_on_its_first_day(t: bt.TestCaseRun) -> None:
    client, li_post, _ = _seeded()
    campaign = "?utm_source=linkedin&utm_medium=social&utm_campaign=ecom-screen"
    events = [
        # starts on 5.10 at 23:58, goes on past midnight
        _event("2026-10-05 23:58:00", "/blog/every-screen-a-decision/", 1759708680000,
               url="https://aito.ai/blog/every-screen-a-decision/" + campaign,
               referrer="https://www.linkedin.com/"),
        _event("2026-10-06 00:01:00", "/pricing/", 1759708680000),
        # started on 4.10, so it is not a 5.10 visit
        _event("2026-10-04 23:59:00", "/docs/", 1759622340000, device_id="dev-early"),
        _event("2026-10-05 00:02:00", "/docs/api/v2/quickstart/", 1759622340000, device_id="dev-early"),
    ]
    for day in ("2026-10-04", "2026-10-05", "2026-10-06"):
        webanalytics.store_day(client, day, events)
    rows = client.query({"from": "web_sessions", "where": {"$and": [
        {"day": {"$gte": "2026-10-04"}}, {"day": {"$lte": "2026-10-06"}}]}, "limit": 100})["hits"]
    t.h1("Rows over the three days")
    for r in sorted(rows, key=lambda r: (r["day"], r["hour"])):
        t.tln(f"{r['day']} {r['hour']:02d}h {r['landing_path']} -> {r.get('next_path')} "
              f"views={r['views']} source={r['source']} linked={r.get('post_id') == li_post}")
    assert len(rows) == 2, f"expected 2 sessions, got {len(rows)}"
    late = next(r for r in rows if r["landing_path"] == "/blog/every-screen-a-decision/")
    assert (late["day"], late["hour"], late["views"], late["next_path"], late["weekday"]) == \
        ("2026-10-05", 23, 2, "/pricing/", "mon"), late
    assert late.get("post_id") == li_post
    early = next(r for r in rows if r["landing_path"] == "/docs/")
    assert (early["day"], early["views"]) == ("2026-10-04", 2), early
    assert not any(r["landing_path"] == "/pricing/" for r in rows), "a fake landing after midnight"
    for day in ("2026-10-04", "2026-10-06"):
        client.delete_entries("web_sessions", {"day": day})
    _clean(client)


def test_odd_events_are_counted_not_fatal(t: bt.TestCaseRun) -> None:
    client, _, _ = _seeded()
    pathless = _event("2026-10-05 08:00:00", "/x/", 1759651200000, device_id="dev-odd")
    pathless["event_type"] = "Viewed Something odd"
    pathless["event_properties"] = {"[Amplitude] Page Title": "Something odd"}
    no_session = [_event("2026-10-05 12:00:00", "/a/", -1, device_id="dev-nosession"),
                  _event("2026-10-05 15:00:00", "/b/", -1, device_id="dev-nosession")]
    t.h1("A Viewed event without a path, and two events without a session")
    report = webanalytics.store_day(client, DAY, [pathless, *no_session])
    t.tln(json.dumps({k: report[k] for k in ("sessions", "mapped", "unmapped", "no_session_events")},
                     sort_keys=True))
    assert report["unmapped"] == {"Viewed (no path)": 1}, report["unmapped"]
    assert (report["sessions"], report["no_session_events"]) == (2, 2), report
    rows = client.query({"from": "web_sessions", "where": {"day": DAY}, "limit": 10})["hits"]
    assert sorted(r["landing_path"] for r in rows) == ["/a/", "/b/"], rows
    _clean(client)


def test_a_failed_upload_keeps_the_old_rows(t: bt.TestCaseRun) -> None:
    client, _, _ = _seeded()
    webanalytics.store_day(client, DAY, _events())
    before = sorted(r["session_key"] for r in _rows(client).values())
    upload = client.upload_batch
    client.upload_batch = lambda table, rows: (_ for _ in ()).throw(RuntimeError("upload died"))
    try:
        webanalytics.store_day(client, DAY, _events())
        raise AssertionError("store_day returned after a failed upload")
    except RuntimeError as e:
        t.h1("A re-pull whose upload fails")
        t.tln(f"raised: {e}")
    finally:
        client.upload_batch = upload
    after = sorted(r["session_key"] for r in _rows(client).values())
    t.tln(f"{len(before)} rows before, {len(after)} after")
    assert after == before, "a failed upload emptied the day"
    _clean(client)


def test_pull_stores_days_independently_and_flags_empty_days(t: bt.TestCaseRun) -> None:
    client, _, _ = _seeded()
    events = _events()

    def fetch(day):
        if day == "2026-10-04":
            raise RuntimeError("Amplitude 503")
        return events if day == DAY else []

    t.h1("Three days, the first fails, the third has no visits")
    reports = webanalytics.pull(client, days=3, today=date(2026, 10, 7), fetch=fetch)
    for r in reports:
        t.tln(json.dumps({k: r.get(k) for k in ("day", "sessions", "error", "empty")}, sort_keys=True))
    by_day = {r["day"]: r for r in reports}
    assert by_day["2026-10-04"]["error"] == "RuntimeError: Amplitude 503"
    assert by_day[DAY]["sessions"] == 5 and not by_day[DAY].get("error")
    assert by_day["2026-10-06"]["empty"] is True
    _clean(client)


def test_paths_and_utm_values_are_redacted(t: bt.TestCaseRun) -> None:
    client, _, _ = _seeded()
    email = "jane" + "@" + "example.test"          # built here, so no tracked file holds one
    token = "9f8e7d6c5b4a39281706f5e4d3c2b1a0"
    events = [
        _event("2026-10-05 07:00:00", f"/unsubscribe/{email}/", 1759647600000, device_id="dev-r1"),
        _event("2026-10-05 07:01:00", f"/reset/{token}", 1759647600000, device_id="dev-r1"),
        _event("2026-10-05 07:30:00", "/blog/", 1759649400000, device_id="dev-r2",
               url=f"https://aito.ai/blog/?utm_source=News%20Letter&utm_campaign={email}"
                   "&utm_medium=" + "x" * 90),
    ]
    rows = webanalytics.sessions_from_events(events, DAY)
    t.h1("Stored paths and utm values")
    for r in rows:
        t.tln(json.dumps({k: r[k] for k in ("pages", "utm_source", "utm_medium", "utm_campaign")},
                         sort_keys=True))
    leaks = _leaks(rows)
    t.tln(f"leaks: {leaks}")
    assert not leaks, leaks
    first = next(r for r in rows if r["landing_path"].startswith("/unsubscribe"))
    assert first["pages"] == "/unsubscribe/<email>/ /reset/<token>", first["pages"]
    blog = next(r for r in rows if r["landing_path"] == "/blog/")
    assert (blog["utm_source"], blog["utm_campaign"], blog["utm_medium"]) == \
        ("news_letter", "<invalid>", "<invalid>"), blog

    t.h1("The same, with the redaction stubbed out, must leak")
    redact = webanalytics._redact_segment
    try:
        webanalytics._redact_segment = lambda segment: segment
        stubbed = webanalytics.sessions_from_events(events, DAY)
    finally:
        webanalytics._redact_segment = redact
    found = _leaks(stubbed)
    for leak in found:
        t.tln(leak.split(" '")[0])      # the kind, not the value: no email in a tracked book
    assert any("email" in f for f in found) and any("token" in f for f in found), found


def test_a_duplicate_slug_links_nothing_and_is_reported(t: bt.TestCaseRun) -> None:
    client, li_post, _ = _seeded()
    twin = client.query({"from": "posts", "where": {"post_id": li_post}, "limit": 1})["hits"][0]
    twin = {**twin, "post_id": "po-twin"}
    client.upload_batch("posts", [twin])          # add_post refuses this; a race would not
    t.h1("Two posts share the slug ecom-screen")
    report = webanalytics.store_day(client, DAY, _events())
    t.tln(json.dumps(report["duplicate_campaigns"], sort_keys=True).replace(li_post, "<li-post>"))
    assert report["duplicate_campaigns"] == {"ecom-screen": sorted([li_post, "po-twin"])}
    li = _rows(client)["Finland"]
    assert li.get("post_id") is None and li.get("link_basis") is None, li
    client.delete_entries("posts", {"post_id": "po-twin"})
    _clean(client)


def test_a_visit_before_the_post_is_not_credited(t: bt.TestCaseRun) -> None:
    client, li_post, _ = _seeded()
    client.update_entries("posts", {"post_id": li_post}, {"posted_at": "2026-10-09"})
    t.h1("The ecom-screen post went out on 9.10, after the 5.10 visit")
    report = webanalytics.store_day(client, DAY, _events())
    li = _rows(client)["Finland"]
    t.tln(json.dumps({"post_id": li.get("post_id"), "link_basis": li.get("link_basis"),
                      "before_post": report["before_post"]}, sort_keys=True))
    assert li.get("post_id") is None and report["before_post"] == 1, (li, report)
    _clean(client)


def test_the_weekly_kpis_work_before_web_sessions_exists(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    client.delete_table("web_sessions")
    try:
        t.h1("engagement_kpis on an instance without web_sessions")
        out = engagements.weekly(client, as_of=date(2026, 10, 7), weeks=1)
        t.tln(json.dumps({"web": out.get("web"),
                          "week": {k: out["weeks"][-1][k] for k in ("web_sessions",
                                                                    "web_onward_click_rate")}},
                         sort_keys=True))
        assert out["weeks"][-1]["web_sessions"] is None and "not created" in out["web"], out
    finally:
        loaders.create_schema(client)


def test_a_failed_check_after_upload_removes_the_new_run(t: bt.TestCaseRun) -> None:
    client, _, _ = _seeded()
    webanalytics.store_day(client, DAY, _events())
    before = sorted(r["session_key"] for r in _rows(client).values())
    query = client.query

    def miscount(body):
        where = body.get("where") or {}
        if body.get("limit") == 0 and isinstance(where, dict) and "pull_run" in where:
            return {"total": -1, "hits": []}
        return query(body)

    client.query = miscount
    try:
        webanalytics.store_day(client, DAY, _events())
        raise RuntimeError("store_day returned after a failed check")
    except AssertionError as e:
        t.h1("A re-pull whose landed-row check fails")
        t.tln(f"raised: {str(e)[:120]}")
    finally:
        client.query = query
    hits = client.query({"from": "web_sessions", "where": {"day": DAY}, "limit": 1000})["hits"]
    t.tln(f"{len(before)} rows before, {len(hits)} after, runs {len({h['pull_run'] for h in hits})}")
    assert sorted(h["session_key"] for h in hits) == before, "the failed run was left in place"
    _clean(client)


def test_a_second_pull_at_once_is_refused(t: bt.TestCaseRun) -> None:
    client = _client()
    t.h1("A pull while another holds the lock")
    with webanalytics.pull_lock(client):
        try:
            webanalytics.pull(client, days=1, today=date(2026, 10, 6), fetch=lambda d: [])
            raise RuntimeError("a second pull ran")
        except webanalytics.PullLocked as e:
            t.tln(f"refused: {str(e).split(' (lock')[0]}")
    t.h1("Once released, a pull runs")
    reports = webanalytics.pull(client, days=1, today=date(2026, 10, 6), fetch=lambda d: [])
    t.tln(f"{len(reports)} day(s) pulled")
    assert len(reports) == 1


def test_broken_tracking_and_a_stale_table_fail_the_run(t: bt.TestCaseRun) -> None:
    today = date(2026, 10, 10)
    ok = {"day": "2026-10-09", "events_on_day": 40, "sessions": 12, "empty": False}
    renamed = {"day": "2026-10-09", "events_on_day": 40, "sessions": 0, "empty": True}
    quiet = {"day": "2026-10-09", "events_on_day": 0, "sessions": 0, "empty": True}
    failed = {"day": "2026-10-09", "error": "RuntimeError: Amplitude 503"}
    cases = [("a normal day", [ok], "2026-10-09"),
             ("events but no sessions: tracking renamed", [renamed], "2026-10-09"),
             ("a quiet day: a warning only", [quiet], "2026-10-09"),
             ("a day that failed", [failed], "2026-10-09"),
             ("the newest stored day is 3 days old", [ok], "2026-10-07"),
             ("nothing stored at all", [quiet], None)]
    t.h1("Run health")
    got = {}
    for name, reports, newest in cases:
        problems, warnings = webanalytics.health(reports, newest, today)
        got[name] = bool(problems)
        t.tln(f"{name}: problems={problems} warnings={warnings}")
    assert got == {"a normal day": False, "events but no sessions: tracking renamed": True,
                   "a quiet day: a warning only": False, "a day that failed": True,
                   "the newest stored day is 3 days old": True, "nothing stored at all": True}, got


def test_redaction_covers_the_token_shapes(t: bt.TestCaseRun) -> None:
    at = "%" + "40"
    email = "jane" + "@" + "example.test"
    cases = {
        "/invite/3f2b8c1e-9a4d-4e7b-b1c2-0d5e6f7a8b9c": "/invite/<token>",
        "/auth/eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2ln": "/auth/<token>",
        "/r/aB3dE5fG7hJ9kL1mN3pQ": "/r/<token>",
        "/s/Zq8RtY2LmN4pWx6KvB3sD9fH": "/s/<token>",
        f"/unsubscribe/jane{at}example.test": "/unsubscribe/<email>",
        f"/u/{email}": "/u/<email>",
        "/reset/9f8e7d6c5b4a39281706f5e4d3c2b1a0": "/reset/<token>",
        # slugs survive
        "/blog/predictive_database_benchmarks/": "/blog/predictive_database_benchmarks/",
        "/blog/2020-state-of-ai-in-finland-report-highlights/":
            "/blog/2020-state-of-ai-in-finland-report-highlights/",
        "/docs/api/v2/quickstart/": "/docs/api/v2/quickstart/",
        "/blog/aito-v2-generally-available/": "/blog/aito-v2-generally-available/",
    }
    t.h1("_redact_path")
    wrong = {}
    for raw, want in cases.items():
        got = webanalytics._redact_path(raw)
        t.tln(f"{want}  <-  {'(an email)' if '@' in raw or at in raw else raw}")
        if got != want:
            wrong[raw] = got
    assert not wrong, wrong
    t.h1("utm values")
    for raw, want in {"jane.doe.example.com": "<invalid>", "linkedin": "linkedin",
                      "ecom-screen-co": "ecom-screen-co", "News Letter": "news_letter",
                      email: "<invalid>"}.items():
        got = webanalytics._clean_utm(raw)
        t.tln(f"{want}")
        assert got == want, (raw, got)


def test_fetch_reads_the_day_before_and_after(t: bt.TestCaseRun) -> None:
    calls = []

    class Answer:
        status_code = 404
        text = ""

    def get(url, params, auth, timeout):
        calls.append({"url": url, **params})
        return Answer()

    get_, env = webanalytics.requests.get, dict(os.environ)
    webanalytics.requests.get = get
    os.environ.update({"AMPLITUDE_API_KEY": "test-only", "AMPLITUDE_SECRET_KEY": "test-only"})
    try:
        t.h1("A past day: the whole D-1..D+1 window")
        webanalytics.fetch_day(DAY, now=datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc))
        t.h1("Yesterday: the end is clamped to the current hour")
        webanalytics.fetch_day("2026-10-19", now=datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc))
    finally:
        webanalytics.requests.get = get_
        os.environ.clear()
        os.environ.update(env)
    for c in calls:
        t.tln(json.dumps(c, sort_keys=True))
    assert (calls[0]["start"], calls[0]["end"]) == ("20261004T00", "20261006T23"), calls[0]
    assert (calls[1]["start"], calls[1]["end"]) == ("20261018T00", "20261020T09"), calls[1]
    assert calls[0]["url"] == "https://analytics.eu.amplitude.com/api/2/export"


def test_known_source_domains_survive_as_utm(t: bt.TestCaseRun) -> None:
    email = "jane" + "@" + "example.test"
    cases = {"linkedin.com": "linkedin.com", "news.ycombinator.com": "news.ycombinator.com",
             "LinkedIn.com": "linkedin.com", "bing.com": "bing.com",
             # a domain off the list, or one dressed as a known one, stays out
             "jane.doe.example.com": "<invalid>", "linkedin.com.example.test": "<invalid>",
             "evil-linkedin.com": "<invalid>", email: "<invalid>"}
    t.h1("utm values shaped like a domain")
    wrong = {}
    for raw, want in cases.items():
        got = webanalytics._clean_utm(raw)
        t.tln(f"{'(an email)' if '@' in raw else raw} -> {got}")
        if got != want:
            wrong[raw] = got
    assert not wrong, wrong


def test_an_external_referrer_keeps_only_its_domain(t: bt.TestCaseRun) -> None:
    """Previous Page Location is another site's full URL: its path and query
    (search terms, an email in a link, tracking ids) and any user@ part must
    not land. Only the host does, redacted like a path segment."""
    at = "%" + "40"

    def visit(n: int, previous: str) -> dict:
        return {"$insert_id": f"ref-{n}", "event_type": "Page View: /", "session_id": 1000 + n,
                "event_time": f"{DAY} 10:0{n}:00.000000", "device_id": f"dev-ref-{n}",
                "os_name": "Chrome", "device_family": "Windows", "platform": "Web",
                "country": "Finland", "user_properties": {},
                "event_properties": {"[Amplitude] Page Domain": "aito.ai",
                                     "[Amplitude] Page URL": "https://aito.ai/",
                                     "[Amplitude] Page Location": "https://aito.ai/",
                                     "[Amplitude] Previous Page Type": "external",
                                     "[Amplitude] Previous Page Location": previous}}
    cases = {
        f"https://www.google.com/search?q=jane{at}example.test&client=x": "google.com",
        "https://jane:pw" + "@" + "news.ycombinator.com/item?id=4242#c": "news.ycombinator.com",
        "https://www.linkedin.com/feed/update/urn:li:activity:7390000000000000000/": "linkedin.com",
        "https://a1b2c3d4e5f6a7b8c9d0e1f2.tracker.example/x?id=1": "<token>",
    }
    rows = webanalytics.sessions_from_events(
        [visit(i, prev) for i, prev in enumerate(cases)], DAY)
    t.h1("referrer_domain from an external previous page")
    stored = sorted(r["referrer_domain"] for r in rows)
    for value in stored:
        t.tln(f"  {value}")
    assert stored == sorted(cases.values()), stored
    flat = json.dumps(rows)
    for leak in ("jane", "search", "item", "activity", "client", "id=", "pw"):
        assert leak not in flat, f"{leak!r} from a referrer URL landed in a row"
