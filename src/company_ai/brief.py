"""The no-llm brief: the three queries' raw results rendered as text.

Formatting only — every number is Aito's, every line is retrieved. The
format is docs/03-morning-brief.md's, target one phone screen. Exists so
the deterministic core is booktestable and the system stays useful
without a model in the loop.
"""

from datetime import date

from . import analytics, queries, schedule, schema, todos
from .aito import AitoClient

MAX_FOLLOWUPS_SHOWN = 8
DO_NEXT_SHOWN = 5


def current_window(hour: int) -> str:
    """The call window nearest the hour. Windows are named by their start
    time, so this follows whatever windows the deployment configures; for the
    default 0800/1215/1600 it reproduces the old hardcoded boundaries (before
    11 -> 0800, before 15 -> 1215, else 1600) for every hour of the day."""
    now = hour * 60
    return min(schema.call_windows(),
               key=lambda w: (abs(schema.window_minutes(w) - now), w))


def render_brief(
    client: AitoClient, window: str, as_of: date, top_n: int = 5
) -> str:
    changed = queries.what_changed(client, as_of=as_of)
    weekday = schema.WEEKDAYS[as_of.weekday()]
    callable_now, reason = schedule.availability(as_of, window)
    lines = []

    # action-first: the cross-area Now list leads (docs/12). Slip-risk is
    # flagged when high, so the brief warns what's likely to slip.
    lines.append("DO NEXT (today, all areas)")
    do_next = todos.now(client, as_of=as_of, top_n=DO_NEXT_SHOWN).derived["todos"]
    if not do_next:
        lines.append("  nothing open")
    for t in do_next:
        due = "overdue" if t["overdue"] else (f"due {t['due_date']}" if t["due_date"] else t["area"])
        sr = t.get("slip_risk")
        slip = f"  ⚠ slip {sr['p']:.0%}" if sr and sr["p"] >= 0.5 else ""
        lines.append(f"  P{t['priority']} {t['title']}  ({due}){slip}")

    lines.append("")
    lines.append("FOLLOW-UPS (due)")
    followups = changed.derived["follow_ups_due"]
    if not followups:
        lines.append("  none")
    for f in followups[:MAX_FOLLOWUPS_SHOWN]:
        lines.append(f"  {f['name']}, {f['company']}  {f['next_action']}  due {f['due']}")
    if len(followups) > MAX_FOLLOWUPS_SHOWN:
        lines.append(f"  ... and {len(followups) - MAX_FOLLOWUPS_SHOWN} more")

    lines.append("")
    lines.append(f"CALL QUEUE  {window}  {weekday}")
    # the doctrine guardrail: never queue calls into protected/unavailable time
    if not callable_now:
        lines.append(f"  {reason}")
        return "\n".join(lines)
    note = schedule.weekday_note(as_of)
    if note:
        lines.append(f"  ({note})")

    queue = queries.who_to_call(client, window, top_n=top_n, as_of=as_of)
    if not queue.derived:
        lines.append("  empty: everyone eligible is cooling down or pending follow-up")
    for i, c in enumerate(queue.derived, 1):
        why = c["why"]
        phone = "" if c["phone_present"] else "  [no phone]"
        recency = ("never touched" if why["days_since_prev_touch"] == "first"
                   else f"{why['days_since_prev_touch']}d since touch")
        lines.append(
            f"  {i}. {c['name']}, {c['company']}{phone}   $p={c['$p']:.2f}   "
            f"why: {why['segment']} {why['tier']} {why['ai_lifecycle']}, {recency}"
        )
        evidence = queries.opener_context(client, c["contact_id"], top_n=1).derived
        if evidence and evidence[0]["evidence"]["notes"]:
            e = evidence[0]["evidence"]
            lines.append(f"     opener evidence: {e['outcome']}: \"{e['notes']}\"")
        else:
            lines.append("     opener evidence: none yet (cold segment)")

    lines.extend(_segment_read(client, queue.derived))
    return "\n".join(lines)


def _segment_read(client: AitoClient, queue: list[dict]) -> list[str]:
    """A 360 read for the segments in today's queue: each segment's
    conversion rate vs the whole pipeline, and the window it converts best
    in. Tells the operator which queued segments are hot and whether now is
    their best window. All numbers from Aito (analytics.kpi_read)."""
    segments = list(dict.fromkeys(c["why"]["segment"] for c in queue))
    if not segments:
        return []
    pipeline = analytics.kpi_read(client, "conversion", {}).derived["rate"]
    out = ["", f"SEGMENT READ  conversion vs pipeline {pipeline:.0%}"]
    for seg in segments:
        read = analytics.kpi_read(client, "conversion", {"segment": seg}).derived
        options = read["lever"]["options"]
        best = options[0]["value"] if options else "?"
        arrow = "↑" if read["rate"] > pipeline else ("↓" if read["rate"] < pipeline else "=")
        out.append(f"  {seg:<12} {read['rate']:.0%} {arrow}   best window {best}")
    return out
