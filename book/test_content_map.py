"""aito.ai's content map on the web tables (plan C1, td-20261118100112648424).

aito.ai publishes /content-map.json: each page key, written as company-ai
writes it ("/pricing/", "ecommerce.aito.ai/cart"), mapped to an item, kind,
category, subcategory, verticals and domains. Each pull reads the map and puts
items, categories, subcategories, verticals and domains on web_sessions (the
visit's, in order, once each) and on each page step of web_steps, as
whitespace Text, so pooled counts are one _relate (verticals=ERP -> pricing).

A page the map doesn't name is counted, never guessed (rule 3): the session's
unmapped_pages, and the run report's unmapped_pages by page. A map that is
malformed raises with its entry. History is relabelled once from the stored
pages, dry run first. The fixture map (data/fixtures/content_map.json) is
invented, in the published shape. Requires a running Aito instance."""

import json
from pathlib import Path

import booktest as bt

from company_ai import contentmap, relations, webanalytics

MAP_FIXTURE = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "content_map.json"
FIELDS = ("items", "categories", "subcategories", "verticals", "domains")


def _map() -> dict:
    return contentmap.parse(json.loads(MAP_FIXTURE.read_text()))


def _by_country(client) -> dict:
    from book.test_web_analytics import DAY
    hits = client.query({"from": "web_sessions", "where": {"day": DAY}, "limit": 100})["hits"]
    return {h["country"]: h for h in hits}


def _show(t: bt.TestCaseRun, rows: dict) -> None:
    for country in sorted(rows):
        r = rows[country]
        t.tln(f"  {country}: {r['pages']}")
        t.tln("    " + ", ".join(f"{f}={r.get(f)}" for f in (*FIELDS, "unmapped_pages")))


def test_the_map_is_parsed_and_a_bad_entry_raises(t: bt.TestCaseRun) -> None:
    cmap = _map()
    t.h1("The fixture map")
    for key, entry in cmap.items():
        t.tln(f"  {key}: {entry}")
    assert cmap["ecommerce.aito.ai/cart"]["items"] == ["cart-recommendations", "bought-together"]
    assert cmap["/pricing/"]["items"] == ["site:pricing"], "a single item is a list of one"
    t.h1("Refused, naming the entry")
    good = json.loads(MAP_FIXTURE.read_text())
    bad = {
        "an unknown version": {**good, "version": 2},
        "an unknown kind": {"version": 1, "pages": {"/x/": {"item": "x", "kind": "video"}}},
        "an unknown field": {"version": 1, "pages": {"/x/": {"item": "x", "kind": "page", "tags": ["a"]}}},
        "no item": {"version": 1, "pages": {"/x/": {"kind": "page"}}},
        "a value with a space": {"version": 1, "pages": {"/x/": {"item": "x", "kind": "usecase",
                                                                  "verticals": ["Financial services"]}}},
        "a key with a query": {"version": 1, "pages": {"/x/?a=1": {"item": "x", "kind": "page"}}},
    }
    for label, blob in bad.items():
        try:
            contentmap.parse(blob)
            raise AssertionError(f"{label} must be refused")
        except AssertionError as e:
            if "must be refused" in str(e):
                raise
            t.tln(f"  {label}: {e}")


def test_a_pull_labels_sessions_and_steps_from_the_map(t: bt.TestCaseRun) -> None:
    from book.test_web_analytics import DAY, _clean, _events, _seeded
    client, _, _ = _seeded()
    report = webanalytics.store_day(client, DAY, _events(), content_map=_map())
    t.h1("The run report counts the unmapped pages of human visits")
    t.tln(f"  unmapped_pages: {report['unmapped_pages']}")
    assert report["unmapped_pages"] == {"/docs/api/v2/quickstart/": 1, "/signup/": 1}

    rows = _by_country(client)
    t.h1("Sessions")
    _show(t, rows)
    de = rows["Germany"]       # / then the cart demo on another host
    assert de["items"] == "site:home cart-recommendations bought-together"
    assert (de["categories"], de["verticals"], de["domains"]) == ("mixed", "E-commerce", "ecommerce")
    assert de.get("subcategories") is None and de["unmapped_pages"] == 0
    se = rows["Sweden"]        # /docs/ twice, a quickstart the map doesn't name
    assert se["items"] == "site:docs", "once each, in visit order"
    assert se["unmapped_pages"] == 1
    assert rows["Finland"]["unmapped_pages"] == 1          # /signup/
    assert rows["Netherlands"]["unmapped_pages"] == 1      # the probe: on the row, not in the report

    t.h1("Steps: a page step carries its page's labels, an event step none")
    steps = client.query({"from": "web_steps", "where": {"day": DAY, "visitor_key":
                          webanalytics._visitor_key("dev-2a3b4c5d")}, "limit": 100})["hits"]
    steps.sort(key=lambda s: s["n"])
    for s in steps:
        t.tln(f"  n={s['n']} {s['token']:32} items={s.get('items')} verticals={s.get('verticals')}")
    assert [s.get("items") for s in steps] == ["site:home", None,
                                               "cart-recommendations bought-together", None]
    assert steps[2]["verticals"] == "E-commerce"

    t.h1("Pooled counts are one _relate")
    out = relations.relate(client, "web_sessions", {"kpi_sandbox": True}, where={"likely_bot": False},
                           keep=list(FIELDS), top_n=100)
    mine = [r for r in out["relations"] if r["field"] in FIELDS]
    for r in mine:
        t.tln(f"  {r['field']}={r['value']}: {r['rows_with']} visits, rate {r['rate_with']}")
    ecom = next(r for r in mine if (r["field"], r["value"]) == ("verticals", "E-commerce"))
    assert (ecom["rows_with"], ecom["rate_with"]) == (1, 1.0)
    _clean(client)


def test_without_a_map_the_labels_are_unset_not_empty(t: bt.TestCaseRun) -> None:
    """A row stored without the map reads unmapped_pages null: not applied,
    told apart from 0 (every page mapped)."""
    from book.test_web_analytics import DAY, _clean, _events, _seeded
    client, _, _ = _seeded()
    report = webanalytics.store_day(client, DAY, _events())
    rows = _by_country(client)
    t.h1("No map given")
    t.tln(f"  report unmapped_pages: {report['unmapped_pages']}")
    _show(t, rows)
    assert report["unmapped_pages"] is None
    assert all(r.get("unmapped_pages") is None and r.get("items") is None for r in rows.values())
    _clean(client)


def test_pull_reads_the_map_once_and_an_unreachable_map_stores_unlabelled(t: bt.TestCaseRun) -> None:
    """CPO review of #108: an unreachable map doesn't cost the day's visits.
    They're stored unlabelled (unmapped_pages null), the run reports it as a
    problem and exits non-zero, and apply-content-map fills them in later. A
    map that is there but malformed still raises."""
    from datetime import date
    from book.test_web_analytics import DAY, _clean, _events, _seeded
    client, _, _ = _seeded()
    calls = []

    def fetch_map():
        calls.append(1)
        return _map()

    today = date(2026, 10, 7)
    reports = webanalytics.pull(client, days=2, today=today,
                                fetch=lambda d: _events() if d == DAY else [], fetch_map=fetch_map)
    t.h1("Two days, one map read")
    t.tln(f"  map reads: {len(calls)}; days: {[r['day'] for r in reports]}")
    assert len(calls) == 1
    day = next(r for r in reports if r["day"] == DAY)
    assert day["unmapped_pages"] == {"/docs/api/v2/quickstart/": 1, "/signup/": 1}

    t.h1("An unreachable map: the days are stored unlabelled, the run fails")
    _clean(client)

    def unreachable():
        raise contentmap.Unavailable("content map https://aito.ai/content-map.json: HTTP 503")

    reports = webanalytics.pull(client, days=2, today=today,
                                fetch=lambda d: _events() if d == DAY else [], fetch_map=unreachable)
    for r in reports:
        if r["day"] not in {"retention", "web_visitors"}:
            t.tln(f"  {r['day']}: {r.get('error') or ('sessions ' + str(r.get('sessions')))}")
    assert next(r for r in reports if r["day"] == DAY)["sessions"] == 5
    rows = _by_country(client)
    assert len(rows) == 5 and all(r.get("unmapped_pages") is None for r in rows.values())
    problems, _ = webanalytics.health(reports, DAY, today)
    t.tln(f"  problems: {problems}")
    assert any(p.startswith("content_map: ") and "apply-content-map" in p for p in problems)

    t.h1("A malformed map raises, before any day is stored")
    _clean(client)

    def malformed():
        return contentmap.parse({"version": 2, "pages": {}})

    try:
        webanalytics.pull(client, days=2, today=today,
                          fetch=lambda d: _events() if d == DAY else [], fetch_map=malformed)
        raise AssertionError("a malformed map must be refused")
    except AssertionError as e:
        if "must be refused" in str(e):
            raise
        t.tln(f"  {e}")
    assert client.query({"from": "web_sessions", "limit": 0})["total"] == 0
    _clean(client)


def test_history_is_relabelled_once_from_the_stored_pages(t: bt.TestCaseRun) -> None:
    from book.test_web_analytics import DAY, _clean, _events, _seeded
    client, _, _ = _seeded()
    webanalytics.store_day(client, DAY, _events())         # stored before the map existed
    before = _by_country(client)
    t.h1("Dry run: what would change, nothing written")
    plan = webanalytics.apply_content_map(client, _map(), apply=False)
    t.tln(f"  {json.dumps(plan, sort_keys=True)}")
    assert plan["days"] == {DAY: {"sessions": 5, "steps": len(client.query(
        {"from": "web_steps", "where": {"day": DAY}, "limit": 1000})["hits"])}}
    assert plan["unmapped_pages"] == {"/docs/api/v2/quickstart/": 1, "/signup/": 1}
    assert all(r.get("items") is None for r in _by_country(client).values())

    t.h1("Applied: the same labels a pull would have written")
    done = webanalytics.apply_content_map(client, _map(), apply=True)
    t.tln(f"  {json.dumps({k: v for k, v in done.items() if k != 'runs'}, sort_keys=True)}")
    after = _by_country(client)
    _show(t, after)
    assert after["Germany"]["items"] == "site:home cart-recommendations bought-together"
    assert after["Sweden"]["unmapped_pages"] == 1
    labels = {*FIELDS, "unmapped_pages", "pull_run"}
    same = {k for r in (*before.values(), *after.values()) for k in r if not k.startswith("$")} - labels
    assert all(after[c].get(k) == before[c].get(k) for c in before for k in same), "nothing else changes"
    steps = client.query({"from": "web_steps", "where": {"day": DAY}, "limit": 1000})["hits"]
    t.tln(f"  steps: {len(steps)}, runs {len({s['pull_run'] for s in steps})}, "
          f"labelled {sum(bool(s.get('items')) for s in steps)}")
    assert len({s["pull_run"] for s in steps}) == 1
    assert len({r["pull_run"] for r in after.values()}) == 1
    _clean(client)
