# 30 · Outbox (staged outbound, authorised by a human)

**An agent prepared outbound, a human authorised it, it went out on time** — as a
system, not a chat ritual. The outbox is the queue between those two facts: an
agent writes a message into it, the operator approves or strikes it on a phone,
and every outbound is audited whether or not anyone remembers the conversation.

**Nothing in this repo sends mail.** Phase 1 is the table, the staging tools, and
the approval view. No SMTP, no Gmail API, no OAuth — that is deliberate
(`CLAUDE.md`: outbound automation is parked until it is specified and asked for),
and it is why this phase needs zero new credentials.

## Why it exists

On 15.8 seven campaign drafts were staged and most landed as standalone Gmail
drafts instead of replies on the existing threads, because thread ids were not
resolved first. They had to be copied into the right threads by hand. At seven
that is annoying; at forty the machine is worse than useless. So **resolving the
thread is a precondition of staging, not a step someone remembers**.

## The table: `outbox`

One row per intended message. Twenty columns, exactly the spec's:

| Column | Notes |
|---|---|
| `outbox_id` | `ob-<timestamp>` |
| `created`, `updated` | ISO datetime, UTC |
| `channel` | `email` (only, for now) |
| `to`, `cc` | addresses |
| `contact_name`, `company` | so the approval card reads like a person, not a row |
| `subject`, `body` | `body` is the final plain text — no send-time templating |
| `thread_id` | Gmail threadId. Required if any thread exists with this contact |
| `reply_to_message_id` | latest message id in that thread. Required whenever `thread_id` is set |
| `send_after` | ISO datetime, the intended window |
| `class` | `first_touch` \| `re_entry` \| `logistics` \| `campaign` \| `referral_ask` |
| `status` | `staged` → `approved` → `drafted` → `sent`, or `held` \| `struck` |
| `agent` | who staged it (`cro`, …) |
| `rationale` | one line: why this, why now — the line the approval view shows |
| `message_id`, `sent_at` | written back after a send |
| `result` | `replied` \| `bounced` \| `no_reply` — filled by the daily sweep |

It is **app state**, like `chat_messages` and `changelog`: real recipients and
real bodies live in Aito, never in the repo, so there is no seed CSV, no loader,
and no export (docs/06-privacy.md). `create-schema` / `doctor` / the Data sheet
still cover it, because it is in `schema.TABLES`.

Phase 1 writes `staged`, `approved`, and `struck`. `drafted` / `sent` / `held`
and the three send-result columns are valid values with no writer yet — the
later steps fill them.

## The two guards

**1 · The thread is resolved before staging.** `stage_outbox` refuses a
`thread_id` with no `reply_to_message_id` (without it nothing can be threaded),
refuses a reply id with no thread, and refuses to stage with no thread at all
unless the caller passes `no_thread=True` — an explicit claim that the contact's
threads were searched and there genuinely is none. Searching Gmail is the
agent's job (search, then `get_thread`; search results truncate). This repo
cannot check Gmail — it has no credentials and, in phase 1, no business having
any — so what it enforces is that the claim was made deliberately.

**2 · No agent approves its own draft.** Every id staged in a process is
remembered (`outbox.STAGED_IN_SESSION`), and approving one of them through the
agent surface raises. On top of that, `approve_outbox` is **not on the remote MCP
surface** (`remotemcp.REMOTE_DENY`), and both write routes are **operator-only**
in the API's `role_guard`. Striking is never blocked: killing an outbound needs
no ceremony. See *Honest limits* for what this does and does not buy.

## The flow

1. An agent stages rows (`stage_outbox`, `status=staged`).
2. **The operator approves in ai.i** — the Outbox view, `#/outbox`. Each staged
   message is one card: who it is to and at which company, whether it replies on
   a thread or starts a new one, its class, the send window, the one-line
   rationale, and the full body. Three actions: **Approve · Edit · Strike**. On a
   phone they are full-width, 44px targets — one thumb per message, which is the
   entire point.
3. *(Not built)* the daily cron picks up `approved` rows due today, resolves the
   thread, creates a properly-threaded Gmail draft, sets `status=drafted`.
4. *(Not built)* the operator taps send from the drafts folder.
5. *(Not built)* the daily sweep reconciles `in:sent` into `message_id` /
   `sent_at`, and later `result`.

Approving does **not** send, and the view says so. It releases the message to be
drafted into its thread.

## Surfaces

**MCP** (`server.py`) — the agent's half:

- `stage_outbox(to, contact_name, company, subject, body, send_after, msg_class,
  rationale, agent, cc=None, thread_id=None, reply_to_message_id=None,
  no_thread=False)` — `msg_class` is the `class` column (`class` is a Python
  keyword). Writes one `staged` row.
- `outbox_queue(status="staged")` — the queue, soonest send window first; pass
  `null` for everything plus a count per status.
- `approve_outbox(outbox_id, decision, approved_by)` — `approved` or `struck`.
  The human path; an agent cannot use it on a row it staged, and it is off the
  remote surface entirely.

**HTTP** (`api.py`) — the ai.i half:

- `GET /api/outbox?status=staged`
- `PATCH /api/outbox/{outbox_id}` — edit a staged message (operator only)
- `POST /api/outbox/{outbox_id}/decide` `{"decision": "approved"|"struck"}`
  (operator only; the decider is the signed-in Easy Auth identity, never a
  client-supplied name)

The `outbox` columns are fixed by the spec, so **who** decided is recorded in the
change log (`entity=outbox`, `action=approved|struck`, `detail.by`), alongside
the staging and edit entries. Every state change is auditable there.

## The write path, and one engine bug

Staging is a plain insert. A decision or an edit is a `_modify` update **followed
by `optimize`**: on this Aito build the update lands but stays invisible to reads
until the next write to the collection (docs/24, bug 5 — re-probed 2026-08-15,
still reproduces), and an approval the operator cannot see is worse than no
approval. `optimize` is that next write. The row is then read back and the change
asserted, so a write that did not land raises instead of being reported as
success. The rest of the repo works around the same bug with a full-table
rewrite; the outbox does not, because drop-and-reload would put every real
recipient through a delete/restore window for a one-field edit.

## Honest limits

- **Nothing sends.** Steps 3–5 above are unbuilt. `drafted`/`sent`/`held` and
  `message_id`/`sent_at`/`result` have no writer.
- **The thread check is a discipline, not a verification.** Nothing here can ask
  Gmail whether a thread exists; `no_thread=True` is an assertion by the caller.
  A determined agent can lie to it. It converts a silent default into a
  deliberate statement, which is what killed the 15.8 defect.
- **The self-approval guard is process-scoped.** It stops stage-then-approve in
  one call chain. A *local* stdio agent could still approve a row some other
  session staged; what prevents that is that the remote surface has no
  `approve_outbox` at all, the ai.i route is operator-only, and every decision is
  named in the change log. Making it airtight needs an identity on the MCP
  surface, which this instance does not have.
- **`class` does not yet govern anything.** It is recorded so the autonomy ladder
  has something to graduate later (logistics first, and only after four clean
  weeks). No auto-approval exists.
- **The staged-vs-sent metric is available, not surfaced.** `outbox_queue()` with
  no status returns the count per status; nothing charts it yet.

## Tests

`book/test_outbox.py` (6 booktests): staging and the queue the view renders, the
edit, approve/strike including that the decision survives the read-visibility
bug, the self-approval refusal, the thread preconditions, and the loud-input
cases. `frontend/src/outbox.test.jsx` (7): the card's content, the thread flag,
one-tap approve/strike, the edit round-trip, a decided row showing status instead
of buttons, and a refused decision surfacing rather than pretending. The
operator-only routes are proven in `book/test_roles.py`.
