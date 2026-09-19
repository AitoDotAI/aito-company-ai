"""Operator availability and weekday rhythm (operator-ground-truth.md §1).

The brief must never queue a call into protected or unavailable time:
Wednesday morning is protected Aito deep work (Wed 08:00-12:00), and
Thursday is unavailable all day (Sisua). These are hard rules, encoded
once here so the brief gates its call queue on them and the booktest pins
them. The weekday rhythm (Tue books, Fri converses, Mon is weakest) is
softer context, shown but not enforced.
"""

from datetime import date

from . import schema

WEEKDAY_NOTE = {
    "mon": "Monday — historically the weakest call day",
    "tue": "Tuesday — booking day",
    "fri": "Friday — conversation day",
}


def availability(as_of: date, window: str) -> tuple[bool, str]:
    """(callable_now, reason). False means the brief must not surface a call
    queue for this day/window — the reason explains why."""
    weekday = schema.WEEKDAYS[as_of.weekday()]
    if weekday == "thu":
        return False, "Thursday — unavailable (Sisua), no calls today"
    if weekday == "wed" and window == "0800":
        return False, "Wednesday morning — protected (Aito deep work), no calls before noon"
    return True, ""


def weekday_note(as_of: date) -> str:
    return WEEKDAY_NOTE.get(schema.WEEKDAYS[as_of.weekday()], "")
