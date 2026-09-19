"""The outbox — staged outbound, authorised by a human (docs/30-outbox.md).

A read surface over the `outbox` collection (the write path is in log.py:
`stage_outbox`, `update_outbox`, `approve_outbox`), plus the two guards that
make the approval real rather than ceremonial:

  * `check_thread(...)` — a reply must carry the thread it replies to. Staging
    without a `thread_id` requires an explicit "I looked, there is none".
  * `forbid_self_approval(...)` — an agent may not approve what it just staged.
    Every id staged in *this process* is remembered, and approving one of them
    from the agent surface raises. Approval belongs to the operator, in ai.i.

No prediction here (rule 2): an outbox row is content plus a state machine. The
only ranking is chronological — the send window, soonest first.
"""

from dataclasses import dataclass, field
from datetime import datetime

from . import schema
from .aito import AitoClient


class OutboxError(RuntimeError):
    pass


@dataclass
class Result:
    calls: list = field(default_factory=list)
    derived: dict | None = None


# Every outbox_id staged by THIS process. The autonomy rule (docs/30, spec hard
# rule 2) is "only the operator moves staged → approved"; the mechanical half of
# it we can enforce here is that a stage and an approve never happen in one
# agent's call chain. Process-scoped on purpose: it is not a permission system,
# it is a circuit breaker on the one sequence an agent could otherwise run
# unaided. The API path (a signed-in operator in ai.i) is unaffected.
STAGED_IN_SESSION: set[str] = set()


def _ensure(client: AitoClient) -> None:
    """The table must materialise on an instance that predates it (mirrors
    chats/changelog) — staging must never fail because of a missing migration."""
    client.ensure_table("outbox", schema.OUTBOX)


def remember_staged(outbox_id: str) -> None:
    STAGED_IN_SESSION.add(outbox_id)


def forbid_self_approval(outbox_id: str, decision: str, source: str) -> None:
    """Raise if this call chain both staged and now approves the same row.
    Striking is always allowed — killing an outbound needs no ceremony — and so
    is the `ui` source, which is a signed-in operator, not an agent."""
    if decision != "approved" or source == "ui":
        return
    assert outbox_id not in STAGED_IN_SESSION, (
        f"{outbox_id} was staged by this session — an agent cannot approve its own "
        "draft. Approval is the operator's, in the ai.i Outbox view (docs/30)."
    )


def check_thread(thread_id: str | None, reply_to_message_id: str | None,
                 no_thread: bool) -> None:
    """The precondition this whole feature exists for: a reply is drafted onto
    the thread it belongs to. `thread_id` without the latest message id cannot
    be threaded (In-Reply-To/References need it), and staging with no thread at
    all is only allowed as an explicit claim that the contact's threads were
    searched and there genuinely is none — never as a default (spec hard rule 1;
    seven misfiled drafts on 15.8 are why)."""
    if thread_id:
        assert reply_to_message_id, (
            f"thread_id {thread_id!r} needs reply_to_message_id (the latest message in "
            "that thread) — without it the draft cannot be threaded"
        )
        return
    assert not reply_to_message_id, (
        "reply_to_message_id without thread_id: resolve the thread first"
    )
    assert no_thread, (
        "no thread_id: resolve the contact's threads first (search, then get_thread — "
        "search results truncate). If there genuinely is no prior thread, stage with "
        "no_thread=True to say so explicitly."
    )


def parse_ts(value: str, field_name: str) -> str:
    """An ISO date or datetime, echoed back. Anything else raises (rule 3)."""
    try:
        datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise AssertionError(f"{field_name} is not an ISO date/datetime: {value!r}")
    return value


def normalise(row: dict) -> dict:
    """Aito omits absent nullable keys — fill them so every consumer (UI, MCP,
    booktest) reads a complete, stable shape."""
    return {**{k: None for k in schema.OUTBOX["columns"]}, **row}


def queue(client: AitoClient, status: str | None = None, limit: int = 500) -> Result:
    """The outbox, soonest send window first. `status` narrows it (the approval
    view asks for `staged`). Returns the rows plus a count per status, which is
    the staged-vs-sent signal: a staged pile that never becomes sent is this
    design decaying, and it should be visible without a query."""
    if status is not None:
        assert status in schema.OUTBOX_STATUS, \
            f"unknown status {status!r}; have {sorted(schema.OUTBOX_STATUS)}"
    _ensure(client)
    result = Result()
    request = {"from": "outbox", "limit": limit}
    if status:
        request["where"] = {"status": status}
    response = client.query(request)
    result.calls.append(("_query", request, response))

    rows = [normalise(r) for r in response["hits"]]
    rows.sort(key=lambda r: (r.get("send_after") or "", r.get("created") or "",
                             r["outbox_id"]))

    counts = {}
    if status:
        counts[status] = len(rows)
    else:
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
    result.derived = {"count": len(rows), "counts": counts, "rows": rows}
    return result


def read(client: AitoClient, outbox_id: str) -> dict:
    """One outbox row by id."""
    _ensure(client)
    hits = client.query({"from": "outbox", "where": {"outbox_id": outbox_id},
                         "limit": 1})["hits"]
    if not hits:
        raise OutboxError(f"no such outbox row: {outbox_id!r}")
    return normalise(hits[0])
