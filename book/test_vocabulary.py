"""Another company's vocabulary (schema.OVERRIDABLE, docs/32).

Everything in schema.py is this repository's own business written down:
customers segmented into {accounting, erp, ecommerce, …}, deals blocked by
`consultant_lock`. Rule 3 turns each of those into a hard gate, so before this
existed another company's very first CSV row raised and the product was
unusable on their data — the one thing standing between a reader and a trial.

The gate stays strict. Only the vocabulary moves, and only the sets nothing
branches on.
"""

import json

import booktest as bt

from company_ai import schema


def _vocab(t, spec):
    """Reload schema with a vocabulary file in place, and hand back the module."""
    import importlib
    import os
    import tempfile
    fd = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(spec, fd)
    fd.close()
    before = os.environ.get("COMPANY_AI_VOCABULARY")
    os.environ["COMPANY_AI_VOCABULARY"] = fd.name
    try:
        return importlib.reload(schema)
    finally:
        if before is None:
            os.environ.pop("COMPANY_AI_VOCABULARY", None)
        else:
            os.environ["COMPANY_AI_VOCABULARY"] = before


def test_a_company_brings_its_own_vocabulary(t: bt.TestCaseRun) -> None:
    import importlib
    t.h1("the default vocabulary is this repository's own business")
    t.tln(f"SEGMENTS: {sorted(schema.SEGMENTS)}")

    t.h1("a consultancy's taxonomy replaces it")
    s = _vocab(t, {"SEGMENTS": ["public-sector", "retail", "industry", "other"],
                   "TIERS": ["strategic", "growth", "long-tail"],
                   "DEAL_BLOCKERS": ["none", "procurement", "framework-agreement"]})
    t.tln(f"SEGMENTS:      {sorted(s.SEGMENTS)}")
    t.tln(f"TIERS:         {sorted(s.TIERS)}")
    t.tln(f"DEAL_BLOCKERS: {sorted(s.DEAL_BLOCKERS)}")
    t.tln(f"untouched sets keep their defaults — SOURCES: {sorted(s.SOURCES)}")

    t.h1("and their rows load, where before they raised")
    from company_ai import loaders
    importlib.reload(loaders)
    row = {c: "x" for c in s.CONTACTS["columns"] if c not in loaders.DERIVED_CONTACT_COLUMNS}
    row.update({"segment": "public-sector", "tier": "strategic", "source": "referral",
                "ai_lifecycle": "none", "phone_present": "true", "email_present": "true",
                "created": "2026-01-01", "notes_tags": ""})
    try:
        parsed = loaders.parse_rolodex_row(dict(row))
        t.tln(f"a public-sector contact parses: segment={parsed['segment']!r}")
    except Exception as e:                       # pragma: no cover - the point of the test
        t.tln(f"REJECTED (wrong): {str(e)[:100]}")

    importlib.reload(schema)
    importlib.reload(loaders)


def test_structural_sets_cannot_be_overridden(t: bt.TestCaseRun) -> None:
    t.h1("code branches on these, so replacing them would break, not configure")
    # a deal is `won` because its stage is closed_won; the views are keyed on
    # todo areas. (WINDOWS used to be here, until the code stopped reading them.)
    for name in ["DEAL_STAGES", "TODO_AREAS", "TODO_STATUS", "USER_ROLES"]:
        t.tln(f"{name:14} overridable: {name in schema.OVERRIDABLE}")

    t.h1("naming one is refused, not quietly ignored")
    try:
        _vocab(t, {"DEAL_STAGES": ["lead", "won"]})
        t.tln("accepted (WRONG)")
    except AssertionError as e:
        t.tln(str(e).split(":", 1)[1].strip()[:150])
    finally:
        import importlib
        importlib.reload(schema)

    t.h1("so is a set that does not exist at all")
    try:
        _vocab(t, {"CUSTOMER_MOODS": ["happy"]})
        t.tln("accepted (WRONG)")
    except AssertionError as e:
        t.tln("refused, and says which sets are available")
    finally:
        import importlib
        importlib.reload(schema)


def test_defaults_derive_from_the_configured_vocabulary(t: bt.TestCaseRun) -> None:
    t.h1("a surface that scores 'the usual platform' must not assume LinkedIn")
    t.tln(f"default platform, as shipped: {schema.default_platform()}")
    s = _vocab(t, {"PLATFORMS": ["blog", "newsletter"]})
    t.tln(f"for a deployment that does not use LinkedIn: {s.default_platform()}")
    t.tln(f"the POST_CHANNELS alias tracks it: {s.POST_CHANNELS == s.PLATFORMS}")
    import importlib
    importlib.reload(schema)


def test_a_company_brings_its_own_working_week(t: bt.TestCaseRun) -> None:
    """The call windows and the operator's week used to be hardcoded — "Thursday
    is unavailable (Sisua)", "Wednesday morning is protected" — which made one
    person's calendar part of the product."""
    import importlib
    from datetime import date

    from company_ai import brief, schedule

    t.h1("as shipped: this repository's operator")
    t.tln(f"call windows: {schema.call_windows()}")
    for day in sorted(schema.UNAVAILABLE):
        t.tln(f"unavailable {day}: {schema.UNAVAILABLE[day]['windows']}")

    t.h1("another company: different windows, no blocked days, its own rhythm")
    s = _vocab(t, {"WINDOWS": ["0900", "1330", "1530"],
                   "UNAVAILABLE": {},
                   "WEEKDAY_NOTES": {"mon": "Monday — pipeline review"}})
    importlib.reload(schedule)
    importlib.reload(brief)
    try:
        t.tln(f"call windows: {s.call_windows()}  (the catch-all stays: {'other' in s.WINDOWS})")
        t.tln(f"the brief at 08h, 12h, 16h picks: "
              f"{[brief.current_window(h) for h in (8, 12, 16)]}")
        thursday = date(2026, 6, 11)
        t.tln(f"Thursday 0900 callable: {schedule.availability(thursday, '0900')[0]}")
        t.tln(f"Monday note: {schedule.weekday_note(date(2026, 6, 8))!r}")
    finally:
        importlib.reload(schema)
        importlib.reload(schedule)
        importlib.reload(brief)


def test_a_malformed_working_week_is_refused(t: bt.TestCaseRun) -> None:
    import importlib
    t.h1("each mistake names itself instead of silently doing nothing")
    cases = {
        "a window that is not a time": {"WINDOWS": ["morning"]},
        "a blocked window that does not exist": {"WINDOWS": ["0900"],
                                                 "UNAVAILABLE": {"wed": {"windows": ["0800"],
                                                                         "reason": "x"}}},
        "a weekday that is not one": {"UNAVAILABLE": {"wednesday": {"windows": "all",
                                                                    "reason": "x"}}},
        "a block with no reason": {"UNAVAILABLE": {"fri": {"windows": "all"}}},
    }
    for label, spec in cases.items():
        try:
            _vocab(t, spec)
            t.tln(f"{label}: accepted (WRONG)")
        except AssertionError as e:
            t.tln(f"{label}: {str(e).split(': ', 1)[1][:110]}")
        finally:
            importlib.reload(schema)
