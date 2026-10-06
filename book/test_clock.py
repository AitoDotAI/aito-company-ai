"""The date reads reckon from (src/company_ai/clock.py).

A fixed demo dataset rots: its newest row recedes from today until every deal
reads as stalled and every todo as overdue, and the Now view's ranking stops
meaning anything. The fix is to declare the date the dataset reckons from
rather than to move the data toward today (which drifts on every reseed) or to
override the process clock (which would make write stamps lie).

These tests pin the three properties that keep it honest: off by default,
reads-only, and loud when misconfigured.
"""

import os
from datetime import date

import booktest as bt

from company_ai import clock
from company_ai.config import Config, _parse_as_of


def _with_env(value, fn):
    """Run fn with COMPANY_AI_AS_OF set (or cleared), then restore."""
    before = os.environ.get("COMPANY_AI_AS_OF")
    if value is None:
        os.environ.pop("COMPANY_AI_AS_OF", None)
    else:
        os.environ["COMPANY_AI_AS_OF"] = value
    try:
        return fn()
    finally:
        if before is None:
            os.environ.pop("COMPANY_AI_AS_OF", None)
        else:
            os.environ["COMPANY_AI_AS_OF"] = before


def test_off_unless_configured(t: bt.TestCaseRun) -> None:
    t.h1("unset: reads use the real clock")
    unset = _with_env(None, lambda: (clock.reckoning(), clock.today() == date.today()))
    t.tln(f"reckoning: {unset[0]}")
    t.tln(f"today() is the real date: {unset[1]}")
    t.tln("a live instance cannot drift into a fake date by accident")

    t.h1("set: reads reckon from that date")
    got = _with_env("2026-06-12", lambda: (clock.reckoning(), clock.today()))
    t.tln(f"reckoning: {got[0]}")
    t.tln(f"today():   {got[1]}")
    t.tln(f"differs from the real clock: {got[1] != date.today()}")


def test_a_bad_value_raises_rather_than_falling_back(t: bt.TestCaseRun) -> None:
    t.h1("a set-but-unparseable value is a configuration error")
    # silently falling back to today() would leave a demo reckoning from the
    # wrong date while looking like working software (rule 3).
    for raw in ["yesterday", "2026-13-01", "12/06/2026"]:
        try:
            _parse_as_of(raw)
            t.tln(f"{raw!r}: accepted (WRONG)")
        except AssertionError as e:
            t.tln(f"{raw!r}: {e}")

    t.h1("blank and whitespace mean 'use the real clock'")
    for raw in ["", "   "]:
        t.tln(f"{raw!r}: {_parse_as_of(raw)}")


def test_write_stamps_keep_the_real_clock(t: bt.TestCaseRun) -> None:
    t.h1("the reckoning date is READ-ONLY")
    # log.py stamps created / ts / last_done from date.today() directly, and is
    # deliberately NOT routed through clock.today(): a back-dated changelog
    # would corrupt the audit trail the system is supposed to be honest about.
    import inspect

    from company_ai import log
    src = inspect.getsource(log)
    t.tln(f"log.py calls clock.today(): {'clock.today()' in src}")
    t.tln(f"log.py still stamps from date.today(): {'date.today()' in src}")

    for mod_name in ["todos", "deals", "queries", "routines", "board"]:
        mod = __import__(f"company_ai.{mod_name}", fromlist=[mod_name])
        src = inspect.getsource(mod)
        t.tln(f"{mod_name}: reads reckon from clock = {'clock.today()' in src}")


def test_agents_over_mcp_see_the_same_now_as_the_dashboard(t: bt.TestCaseRun) -> None:
    """who_to_call and what_changed used to pass date.today() explicitly, so with
    a reckoning date set an agent over MCP compared against a different "now"
    than the dashboard showed. Checked by capturing the date each tool passes."""
    from company_ai import queries, server

    seen = {}

    class _Derived:
        derived = {}

    def capture(name):
        def fn(*args, **kwargs):
            seen[name] = kwargs.get("as_of")
            return _Derived()
        return fn

    originals = (queries.who_to_call, queries.what_changed, server._client)
    queries.who_to_call, queries.what_changed = capture("who_to_call"), capture("what_changed")
    server._client = lambda: None
    try:
        def call(tool, *a):
            return getattr(server, tool).fn(*a) if hasattr(getattr(server, tool), "fn") \
                else getattr(server, tool)(*a)
        _with_env("2026-06-12", lambda: (call("who_to_call", "1215"), call("what_changed")))
    finally:
        queries.who_to_call, queries.what_changed, server._client = originals
    for name in ("who_to_call", "what_changed"):
        t.tln(f"{name:12} reckons from: {seen.get(name)}")
