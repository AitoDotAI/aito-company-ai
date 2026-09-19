# 27 · Users & assignees (from solo to a small team)

The app began as a *one-person* company's agent (CLAUDE.md). This adds the
minimum for a second person — an SDR — to work alongside the operator: a **user**
each, an **assignee** on the work they own, and a **"My work"** lane. It is a
deliberate expansion of scope (a new decision domain), kept small and honest:
shared CRM, focused views, no heavyweight permission system.

## Auth is not app code

`ai.example.com` is an Azure App Service gated by **Entra Easy Auth**
(`aito-azure/scripts/deployment/setup-company-ai-auth.sh`). Login happens *in
front of* the container; the platform passes the signed-in identity to the app
as headers (`X-MS-CLIENT-PRINCIPAL-NAME` = the user's email). So:

- **Adding a person = an identity decision, not app code.** Give the SDR a
  Microsoft account (or add her to the tenant / as a guest); Easy Auth lets her
  in. A non-Microsoft path (Entra email one-time-passcode, Google) would be the
  same layer — still config, not app code — but is unneeded once she has an
  account. The app never builds or owns auth (and never sends auth email — that
  stays parked).
- **The app only *reads* identity.** It maps the header's email to a `users`
  row to know *who* and *what role*. No session, no password, no login screen.

## The model

```
users (collection)
  user_id   String  id, "u_operator" / "u_<slug>"
  name      Text
  email     String  matches the Easy Auth identity (lowercased)
  role      String  operator | sdr            (USER_ROLES)
  active    Boolean
  created   String
```

And an **`assignee`** column (nullable `user_id`, validated against `users` on
write — rule 3) added to the work an SDR owns:

- **contacts** — lead ownership ("my leads")
- **todos** — task assignment ("my tasks")
- **deals** — pipeline ownership ("my deals")

`assignee` is a **workflow filter, not a security boundary.** Both users see the
whole shared CRM; assignment just powers focus. Hard per-user data isolation is
out of scope (and wrong for a two-person team).

## Surfaces

- **Who am I.** `GET /api/me` resolves the Easy Auth header → the `users` row
  (falling back to the configured operator locally / when no header is present).
  The header shows the signed-in name + role.
- **My work.** A view (and an assignee filter on the area views) that narrows
  contacts / todos / deals to the current user — "what's mine to do."
- **Assigning.** An assignee picker on the item editors; MCP `assign` and the
  API PATCH set it. The agent can assign too ("give these new leads to <SDR>").
- **Users admin.** A small editable list (operator adds the SDR, sets email +
  role). Seeded with the operator.

## Identity resolution (the one subtle bit)

`current_user(request)`:
1. Read `X-MS-CLIENT-PRINCIPAL-NAME` (Easy Auth). Lowercase it.
2. Match it to an active `users.email`. Found → that user (role and all).
3. No header (local dev, or the API hit without the proxy) → the **operator**
   (`COMPANY_AI_OPERATOR_EMAIL`, else the first operator in `users`). Easy Auth
   already restricts *who* can reach the app, so an unmapped-but-authenticated
   identity is trusted-but-unknown → treated as an SDR (least privilege) once
   role enforcement lands, never silently made operator.

## Phasing

- **Phase 1 (this).** The data model, assignment, `/api/me`, the assignee
  filters + My work, users admin, and the header identity. Fully usable: assign
  work, each person filters to theirs. Role is *stored* but not yet *enforced*.
- **Phase 2 (built).** Role-based write enforcement — an `sdr` is limited to
  read + safe writes; the `operator` keeps everything. Enforced by one central
  server-side middleware (`api._OPERATOR_ONLY` + `role_guard`) so a missed
  per-endpoint guard can't open a hole: **operator-only** is the destructive set
  (delete a document, remove an advisor) and the admin set (add/
  edit users, create/edit routine definitions, the composer runs, rebuild the
  search index) → 403 for an SDR. Everything else (log, add/edit contacts/deals/
  todos/documents, assign, tick/run routines, search) is a safe write the SDR
  may do. Mirrored in the UI (the Team admin add/edit is operator-only). The
  same read+safe-writes spirit as the remote MCP's `REMOTE_DENY`.

## Not built

Per-user data isolation, teams larger than a handful, per-user Aito predictions
(e.g. "which SDR closes which segment best" — a natural rule-2 query later), and
any auth inside the app. All parked; none needed for two people sharing a CRM.
