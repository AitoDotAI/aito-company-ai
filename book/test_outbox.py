"""Outbox gate (docs/30-outbox.md): an agent stages outbound, a human authorises
it, and nothing in between is implicit.

Covers the staging write, the queue read the approval view renders, the edit, the
staged → approved / struck decision (including that the change survives the
`_modify` read-visibility bug), and the loud-failure cases that are the point of
the feature: an unresolved thread, an unknown class, a self-approval, a decision
on a row that is no longer staged. Requires a running Aito instance.

Addresses here are @example.com — RFC 2606 reserved, and the privacy gate keeps
real recipients out of the repo (docs/06); real ones live only in Aito.
"""

import booktest as bt

from company_ai import loaders, log, outbox
from company_ai.aito import AitoClient
from company_ai.config import Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _mask(text: str, *ids: str) -> str:
    """Outbox ids are timestamped, so an error message quoting one would make the
    snapshot differ on every run. Mask them; the sentence is what's reviewed."""
    for i in ids:
        text = text.replace(i, "<outbox_id>")
    return text


def _fresh(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.clear_table(client, "outbox")
    outbox.STAGED_IN_SESSION.clear()


def _stage_reply(client: AitoClient, **over) -> dict:
    kwargs = dict(
        to="pia.virtanen@example.com", contact_name="Pia Virtanen", company="Globex",
        subject="Re: pilot scope", body="Hi Pia,\n\nHere is the scope we discussed.\n",
        send_after="2026-08-18T08:00:00", outbox_class="re_entry",
        rationale="Thread went quiet after the 17.6 meeting; pilot scope was the open item.",
        agent="cro", thread_id="thr-77", reply_to_message_id="msg-104",
    )
    kwargs.update(over)
    return log.stage_outbox(client, **kwargs)


def test_stage_then_queue(t: bt.TestCaseRun) -> None:
    client = _client()
    _fresh(client)

    t.h1("An agent stages two messages — a threaded reply and a genuine first touch")
    reply = _stage_reply(client)
    first = log.stage_outbox(
        client, to="ceo@example.com", contact_name="Olli Mäki", company="Initech",
        subject="Predictive layer for your supplier data",
        body="Olli,\n\nOne question about how you route supplier rows today.\n",
        send_after="2026-08-19T08:30:00", outbox_class="first_touch",
        rationale="No prior thread; trigger is their new AI announcement.",
        agent="cro", no_thread=True)
    for row in (reply, first):
        t.tln(f"{row['outbox_id'][:3]}… status={row['status']} class={row['class']} "
              f"thread={row['thread_id']} reply_to={row['reply_to_message_id']}")

    t.h1("The queue the approval view renders — soonest send window first")
    queue = outbox.queue(client, status="staged").derived
    t.tln(f"count={queue['count']} counts={queue['counts']}")
    for m in queue["rows"]:
        t.tln(f"  {m['send_after']}  {m['company']:8} [{m['class']:11}] {m['subject']}")
        t.tln(f"      why: {m['rationale']}")

    t.h1("Every column the spec names is present on a row")
    t.tln(str(sorted(queue["rows"][0])))


def test_approve_and_strike(t: bt.TestCaseRun) -> None:
    client = _client()
    _fresh(client)
    keep = _stage_reply(client)
    drop = _stage_reply(client, subject="Re: pricing", rationale="Duplicate of the scope mail.")

    t.h1("The operator approves one and strikes the other (the ai.i path)")
    # source='ui' is the signed-in operator in ai.i; approved_by is recorded in
    # the change log, since the outbox columns are fixed by the spec.
    approved = log.approve_outbox(client, keep["outbox_id"], "approved",
                                  approved_by="operator", source="ui")
    struck = log.approve_outbox(client, drop["outbox_id"], "struck",
                                approved_by="operator", source="ui")
    t.tln(f"approved: status={approved['status']} updated>created={approved['updated'] >= approved['created']}")
    t.tln(f"struck:   status={struck['status']}")

    t.h1("The decision is visible to the next read (the _modify flush, docs/24 bug 5)")
    # Without the optimize flush the update lands but reads keep returning the
    # stale row — an approval the operator cannot see is worse than no approval.
    after = {m["outbox_id"]: m["status"] for m in outbox.queue(client).derived["rows"]}
    t.tln(f"statuses now: {sorted(after.values())}")
    assert after[keep["outbox_id"]] == "approved"
    assert after[drop["outbox_id"]] == "struck"
    t.tln(f"staged remaining: {outbox.queue(client, status='staged').derived['count']}")

    t.h1("A row that is no longer staged is not re-decided")
    try:
        log.approve_outbox(client, keep["outbox_id"], "struck", approved_by="operator", source="ui")
        raise RuntimeError("re-decided a non-staged row")
    except AssertionError as e:
        t.tln(_mask(str(e), keep["outbox_id"]))


def test_edit_before_approving(t: bt.TestCaseRun) -> None:
    client = _client()
    _fresh(client)
    row = _stage_reply(client)

    t.h1("Edit the text and the window, then approve what was actually read")
    edited = log.update_outbox(client, row["outbox_id"], {
        "subject": "Re: pilot scope (revised)",
        "body": "Hi Pia,\n\nShorter version: here is the scope.\n",
        "send_after": "2026-08-19T08:00:00",
    })
    t.tln(f"subject: {edited['subject']}")
    t.tln(f"send_after: {edited['send_after']}")
    t.tln(f"body: {edited['body']!r}")

    t.h1("Only a staged message is editable")
    log.approve_outbox(client, row["outbox_id"], "approved", approved_by="operator", source="ui")
    try:
        log.update_outbox(client, row["outbox_id"], {"subject": "sneaking a change in"})
        raise RuntimeError("edited an approved message")
    except AssertionError as e:
        t.tln(_mask(str(e), row["outbox_id"]))

    t.h1("A field outside the editable set raises, never silently applies")
    for changes in ({"status": "sent"}, {"agent": "someone_else"}):
        try:
            log.update_outbox(client, row["outbox_id"], changes)
            raise RuntimeError(f"accepted {changes}")
        except AssertionError as e:
            t.tln(str(e).split(";")[0])


def test_agent_cannot_approve_its_own_draft(t: bt.TestCaseRun) -> None:
    client = _client()
    _fresh(client)
    row = _stage_reply(client)

    t.h1("Staged and approved in one call chain — refused (spec hard rule 2)")
    try:
        log.approve_outbox(client, row["outbox_id"], "approved",
                           approved_by="cro", source="mcp")
        raise RuntimeError("an agent approved its own draft")
    except AssertionError as e:
        t.tln(_mask(str(e), row["outbox_id"]))

    t.h1("Striking its own draft is fine — killing an outbound needs no ceremony")
    struck = log.approve_outbox(client, row["outbox_id"], "struck",
                                approved_by="cro", source="mcp")
    t.tln(f"status={struck['status']}")

    t.h1("A decision must name its decider")
    other = _stage_reply(client)
    try:
        log.approve_outbox(client, other["outbox_id"], "approved", approved_by="  ", source="ui")
        raise RuntimeError("approved with no decider")
    except AssertionError as e:
        t.tln(str(e))


def test_thread_is_a_precondition(t: bt.TestCaseRun) -> None:
    client = _client()
    _fresh(client)

    t.h1("Staging refuses to guess at the thread (the 15.8 defect)")
    cases = {
        "no thread, no claim": {"thread_id": None, "reply_to_message_id": None},
        "thread without the message id": {"thread_id": "thr-77", "reply_to_message_id": None},
        "message id without a thread": {"thread_id": None, "reply_to_message_id": "msg-104"},
    }
    for label, over in cases.items():
        try:
            _stage_reply(client, **over)
            raise RuntimeError(f"{label}: was accepted")
        except AssertionError as e:
            t.tln(f"{label}: {e}")

    t.h1("An explicit no_thread=True is the only way to start a new conversation")
    row = _stage_reply(client, thread_id=None, reply_to_message_id=None, no_thread=True)
    t.tln(f"staged with thread_id={row['thread_id']!r}")


def test_bad_input_raises(t: bt.TestCaseRun) -> None:
    client = _client()
    _fresh(client)

    t.h1("Unknown enum values, empty required fields, and leftover templating (rule 3)")
    cases = {
        "unknown class": {"outbox_class": "newsletter"},
        "unknown channel": {"channel": "linkedin"},
        "empty rationale": {"rationale": ""},
        "not an address": {"to": "pia at example dot com"},
        "unresolved placeholder": {"body": "Hi {{first_name}}, quick question."},
        "send_after not a date": {"send_after": "next tuesday"},
    }
    for label, over in cases.items():
        try:
            _stage_reply(client, **over)
            raise RuntimeError(f"{label}: was accepted")
        except AssertionError as e:
            t.tln(f"{label}: {str(e).split(';')[0]}")

    t.h1("An unknown status filter on the queue raises rather than returning everything")
    try:
        outbox.queue(client, status="pending")
        raise RuntimeError("accepted an unknown status")
    except AssertionError as e:
        t.tln(str(e))
