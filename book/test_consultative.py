"""The front page's profile questions on the session (plan C2, docs/44
decision 2, td-20261118100113236668).

aito.ai's consultative layer asks a visitor what they're after (interests:
tech, usecases, ai), their domain and their stage, and sends one Amplitude
event per step ("Consultative: intro shown/interest/domain/submit/skip",
"Consultative: stage", "Consultative: health"). The pull keeps the visit's
answers on its web_sessions row: interests, domain, stage, and the furthest
intro step reached. Every value is from a fixed set; anything else raises
with the event (rule 3).

The visitor's own sentence (`words`, `sentence` on the submit event) never
lands: the pull reads only the allow-listed properties, and the book proves
it with a fixture that carries both. The fixture
(data/fixtures/amplitude_consultative_2026-11-20.jsonl) is invented, in the
shape aito.ai's consultative/profile.mjs sends. Requires a running Aito
instance."""

import copy
import json
from pathlib import Path

import booktest as bt

from company_ai import relations, schema, webanalytics

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "amplitude_consultative_2026-11-20.jsonl"
DAY = "2026-11-20"
FIELDS = ("interests", "domain", "stage", "intro_reached")
SENTENCE = "We run our own ERP and code 40k invoices a month"


def _events() -> list[dict]:
    return [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]


def _rows(client) -> dict:
    hits = client.query({"from": "web_sessions", "where": {"day": DAY}, "limit": 100})["hits"]
    return {h["country"]: h for h in hits}


def test_a_visit_keeps_its_answers(t: bt.TestCaseRun) -> None:
    from book.test_web_analytics import _clean, _seeded
    client, _, _ = _seeded()
    report = webanalytics.store_day(client, DAY, _events())
    t.h1("The run: no consultative event is new any more")
    t.tln(f"  new_event_types: {report['new_event_types']}")
    assert not any(n.startswith("Consultative: ") for n in report["new_event_types"])

    rows = _rows(client)
    t.h1("Sessions")
    for country in sorted(rows):
        r = rows[country]
        t.tln(f"  {country}: " + ", ".join(f"{f}={r.get(f)}" for f in FIELDS))
    fi = rows["Finland"]
    assert (fi["interests"], fi["domain"], fi["stage"], fi["intro_reached"]) == \
        ("ai tech", "erp", "building", "submit")
    se = rows["Sweden"]          # picked a domain, then skipped; dismissed the stage card
    assert (se.get("interests"), se["domain"], se.get("stage"), se["intro_reached"]) == \
        (None, "ecommerce", None, "skip")
    de = rows["Germany"]         # never saw the questions
    assert all(de.get(f) is None for f in FIELDS)

    t.h1("The steps stay in `events`, as names")
    t.tln(f"  Finland: {fi['events']}")
    assert "consultative_intro_submit" in fi["events"].split()

    t.h1("The visitor's sentence is nowhere")
    stored = json.dumps(client.query({"from": "web_sessions", "limit": 100})["hits"]) + \
        json.dumps(client.query({"from": "web_steps", "limit": 1000})["hits"])
    leaked = [w for w in (SENTENCE, "40k invoices", "words_len") if w in stored]
    t.tln(f"  found: {leaked}")
    assert not leaked

    t.h1("A profile is a segment: one _relate")
    out = relations.relate(client, "web_sessions", {"kpi_pricing_page": True},
                           where={"likely_bot": False}, keep=["interests"], top_n=100)
    mine = [r for r in out["relations"] if r["field"] in FIELDS]
    for r in mine:
        t.tln(f"  {r['field']}={r['value']}: {r['rows_with']} visits, rate {r['rate_with']}, thin {r['thin']}")
    erp = next(r for r in mine if (r["field"], r["value"]) == ("domain", "erp"))
    assert (erp["rows_with"], erp["rate_with"], erp["thin"]) == (1, 1.0, True)
    _clean(client)


def test_a_value_outside_its_set_raises_with_the_event(t: bt.TestCaseRun) -> None:
    t.h1("The fixed sets")
    for name in ("CONSULTATIVE_INTERESTS", "CONSULTATIVE_DOMAINS", "CONSULTATIVE_STAGES", "INTRO_STEPS"):
        t.tln(f"  {name}: {getattr(schema, name)}")
    t.h1("Refused")
    cases = {
        "a domain": ("Consultative: intro domain", "domain", "banking"),
        "an interest": ("Consultative: intro interest", "interests", "tech pricing"),
        "a stage": ("Consultative: stage", "stage", "buying"),
        "an intro step": ("Consultative: intro shown", "step", "opened"),
    }
    for label, (etype, prop, value) in cases.items():
        events = copy.deepcopy(_events())
        target = next(e for e in events if e["event_type"] == etype)
        target["event_properties"][prop] = value
        try:
            webanalytics.sessions_from_events(events, DAY)
            raise AssertionError(f"{label} must be refused")
        except AssertionError as e:
            if "must be refused" in str(e):
                raise
            msg = str(e)
            t.tln(f"  {label}: {msg[:160]}")
            assert target["$insert_id"] in msg, "the message names the event"


def test_the_metric_break_on_21_11_is_marked(t: bt.TestCaseRun) -> None:
    """aito.ai #414 (21.11.2026 ~09:00Z): "intro shown" counts every page load
    with the layer on, so counts across that date don't compare."""
    text = (Path(__file__).resolve().parent.parent / "docs" / "44-web-insights.md").read_text()
    t.h1("docs/44 marks it")
    line = next((ln for ln in text.splitlines() if "21.11.2026" in ln), None)
    t.tln(f"  {line}")
    assert line is not None
