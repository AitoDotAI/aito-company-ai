"""Schedule-doctrine gate (operator-ground-truth.md §1): the brief must
never queue calls on a Thursday (Sisua) or a Wednesday morning (protected
Aito deep work). The availability rules are pure; the gated brief needs a
running Aito instance.
"""

from datetime import date

import booktest as bt

from company_ai import brief, loaders, schedule
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

# June 2026: Mon 15, Tue 16, Wed 17, Thu 18, Fri 19
DAYS = {"mon": date(2026, 6, 15), "tue": date(2026, 6, 16), "wed": date(2026, 6, 17),
        "thu": date(2026, 6, 18), "fri": date(2026, 6, 19)}


def test_availability_rules(t: bt.TestCaseRun) -> None:
    t.h1("availability(weekday, window) and the weekday note")
    for wd, day in DAYS.items():
        for window in ("0800", "1215", "1600"):
            ok, reason = schedule.availability(day, window)
            t.tln(f"  {wd} {window}: {'callable' if ok else 'BLOCKED — ' + reason}")
        note = schedule.weekday_note(day)
        if note:
            t.tln(f"    note: {note}")


def test_brief_suppresses_calls_on_protected_time(t: bt.TestCaseRun) -> None:
    config = Config.from_env()
    client = AitoClient(config.instance_url, config.api_key)
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_touches(client, SEED_DIR)
    loaders.load_todos(client, SEED_DIR)

    t.h1("Thursday 0800 — no call queue")
    text = brief.render_brief(client, "0800", DAYS["thu"])
    t.tln(text.split("CALL QUEUE")[1].strip().splitlines()[0])
    assert "no calls" in text

    t.h1("Wednesday 0800 — protected")
    text = brief.render_brief(client, "0800", DAYS["wed"])
    t.tln(text.split("CALL QUEUE")[1].strip().splitlines()[0])
    assert "protected" in text

    t.h1("Wednesday 1600 — queue runs")
    text = brief.render_brief(client, "1600", DAYS["wed"])
    after = text.split("CALL QUEUE")[1]
    t.tln("queue present: " + str("$p=" in after))
    assert "$p=" in after or "empty:" in after
