"""Operator availability and weekday rhythm, from schema.UNAVAILABLE and
schema.WEEKDAY_NOTES.

The brief must never queue a call into time the operator has ruled out; that
is a hard rule, so it is encoded once here and pinned by a booktest. The
weekday notes are softer context, shown but never enforced. Which days and
windows those are is the deployment's own (docs/32) — the defaults are this
repository's operator, and they used to be hardcoded right here.
"""

from datetime import date

from . import schema


def availability(as_of: date, window: str) -> tuple[bool, str]:
    """(callable_now, reason). False means the brief must not surface a call
    queue for this day/window — the reason explains why."""
    rule = schema.UNAVAILABLE.get(schema.WEEKDAYS[as_of.weekday()])
    if rule and (rule["windows"] == "all" or window in rule["windows"]):
        return False, rule["reason"]
    return True, ""


def weekday_note(as_of: date) -> str:
    return schema.WEEKDAY_NOTES.get(schema.WEEKDAYS[as_of.weekday()], "")
