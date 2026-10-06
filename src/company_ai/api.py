"""FastAPI backend: the JSON contract shared by the React UI and the agent.

This is the human-facing half of the "two faces, one contract" architecture
(docs/08): the React frontend fetches these `/api/*` endpoints, while the
agent reaches the *same* underlying functions through the MCP server
(server.py). Both are thin wrappers over the tested data layer
(analytics / funnels / scorer); nothing predictive is computed here.

Routes return the `.derived` payloads verbatim, so the API shape is exactly
what the data-layer booktests already snapshot. Errors surface as
{"error": ...} with a 500 rather than a blank panel.

  company-ai dashboard            # uvicorn on http://localhost:8770
"""

import json
import sys
import re
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import clock
from . import deals, decisions, documents, experiments, funnels, scorer, schema, sheets, todos
from . import log as logbook
from .analytics import SEGMENT_DIMENSIONS, segment_360
from .aito import AitoClient
from .config import Config

WEB_DIST = Path(__file__).parent / "web_dist"  # the built React app (vite build)

# selector value lists, served so the UI never hardcodes enums
SEGMENT_VALUES = {
    "segment": sorted(schema.SEGMENTS),
    "tier": sorted(schema.TIERS),
    "ai_lifecycle": ["none", "announced", "shipped", "operating"],
    "source": sorted(schema.SOURCES),
}
SCORE_OPTIONS = {
    "platform": sorted(schema.PLATFORMS),
    "tone": sorted(schema.TONES),
    "ai_made": sorted(schema.AI_MADE),
    "format": sorted(schema.POST_FORMATS),
    "link_placement": sorted(schema.LINK_PLACEMENTS),
    "lane": sorted(schema.LANES),
    "topic": sorted(schema.POST_TOPICS),
    "length_bucket": ["short", "medium", "long"],
    "weekday": list(schema.WEEKDAYS),
}


def _guarded(fn):
    """Run a data-layer call, turning any failure into a 500 {error}. The full
    traceback is printed to the server console (visible under `./do dev aito`),
    so a failure isn't only a terse {error} on the client."""
    try:
        return fn()
    except Exception as exc:  # surface the cause, never a blank panel
        print(f"[api] request failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config.from_env()

    # Remote MCP (docs/26): mounted at /mcp for cloud Claude, but only when the
    # env master token is configured — otherwise it isn't mounted at all (fail
    # closed). Auth accepts that master token OR any active named token (docs/28,
    # tokens.verify). Built before the routes so it precedes the SPA catch-all,
    # and its streaming session manager is started via the app lifespan.
    # FAIL-SAFE: the /mcp mount must never take down the dashboard. Building it
    # and running its session-manager lifespan are wrapped so any error is logged
    # (to stderr → the container log) and the app still serves — /mcp just won't
    # be available. Each step logs a marker so a container that hangs/crashes on
    # startup shows exactly how far it got.
    def _log(msg: str) -> None:
        print(f"[remote-mcp] {msg}", file=sys.stderr, flush=True)

    remote_mcp = None
    lifespan = None
    if config.mcp_token:
        try:
            from . import remotemcp, tokens as tokens_mod

            def _verify_mcp_token(presented: str) -> bool:
                return tokens_mod.verify(
                    AitoClient(config.instance_url, config.api_key),
                    presented, config.mcp_token)

            if config.public_url:
                _log(f"building /mcp app WITH OAuth (issuer {config.public_url})…")
                remote_mcp = remotemcp.build_oauth(_verify_mcp_token, config.public_url)
            else:
                _log("building /mcp app (bearer only; set COMPANY_AI_PUBLIC_URL for OAuth)…")
                remote_mcp = remotemcp.build(_verify_mcp_token)
            # (session_manager, app, owned_path_prefixes)
            _log("built OK; /mcp will mount")
        except Exception:
            _log("BUILD FAILED — serving the dashboard WITHOUT /mcp:")
            traceback.print_exc()
            remote_mcp = None

        if remote_mcp is not None:
            @asynccontextmanager
            async def lifespan(_app):
                try:
                    _log("starting streamable-HTTP session manager…")
                    async with remote_mcp[0].run():
                        _log("session manager RUNNING; /mcp live")
                        yield
                except Exception:
                    _log("SESSION MANAGER FAILED — dashboard stays up, /mcp unavailable:")
                    traceback.print_exc()
                    yield   # never block app startup on the MCP

    app = FastAPI(title="aito-company-ai", docs_url="/api/docs",
                  openapi_url="/api/openapi.json", lifespan=lifespan)

    def client() -> AitoClient:
        return AitoClient(config.instance_url, config.api_key)

    # ---- Todos (the action surface): now / pipeline / calendar lenses ----
    @app.get("/api/todos")
    def todos_route(lens: str = "now", area: str = "", slip: int = 0):
        if lens == "now":
            # slip-risk is one _predict per distinct todo profile — a per-row
            # fan-out to a remote instance. Opt-in (?slip=1) while v2 lacks a
            # single-query per-row P() (docs/24); the landing view sorts by
            # urgency (due-date + priority), which needs no prediction.
            return _guarded(lambda: todos.now(client(), with_slip_risk=bool(slip)).derived)
        if lens == "pipeline":
            return _guarded(lambda: todos.pipeline(client(), area).derived)
        if lens == "calendar":
            return _guarded(lambda: todos.calendar(client(), area).derived)
        return JSONResponse({"error": f"unknown lens {lens!r}"}, status_code=400)

    # ---- Todo editing (the dashboard's one write surface: operator CRUD on
    #      its own worklist — not reasoning, so within rule 1's read-only spirit)
    @app.get("/api/todo-options")
    def todo_options():
        def go():
            c = client()
            contacts = c.query({"from": "contacts", "limit": 100000})["hits"]
            dl = c.query({"from": "deals", "limit": 100000})["hits"]
            tds = c.query({"from": "todos", "limit": 100000})["hits"]
            # existing agent lanes/owners (docs/12), so the editor can suggest the
            # lanes already in use rather than making the operator recall a slug.
            return {
                "areas": sorted(schema.TODO_AREAS),
                "action_types": sorted(schema.ACTION_TYPES),
                "statuses": sorted(schema.TODO_STATUS),
                "prep_statuses": sorted(schema.PREP_STATUS),
                "calendar_areas": sorted(schema.CALENDAR_AREAS),
                "deadline_areas": sorted(schema.DEADLINE_AREAS),
                "lanes": sorted({t["role"] for t in tds if t.get("role")}),
                "owners": sorted({t["owner"] for t in tds if t.get("owner")}),
                "contacts": sorted(({"id": c["contact_id"], "name": c["name"],
                                     "company": c["company"]} for c in contacts),
                                   key=lambda x: x["name"]),
                "deals": sorted(({"id": d["deal_id"], "company": d["company"],
                                  "stage": d["stage"]} for d in dl
                                 if d.get("won") is None), key=lambda x: x["company"]),
            }
        return _guarded(go)

    @app.post("/api/todos")
    async def todos_create(request: Request):
        body = await request.json()
        return _guarded(lambda: logbook.add_todo(client(), **body))

    @app.patch("/api/todos/{todo_id}")
    async def todos_update(todo_id: str, request: Request):
        changes = await request.json()
        return _guarded(lambda: logbook.update_todo(client(), todo_id, changes))

    @app.post("/api/todos/{todo_id}/complete")
    async def todos_complete(todo_id: str, request: Request):
        body = await request.json() if await request.body() else {}
        return _guarded(lambda: logbook.complete_todo(client(), todo_id, **body))

    @app.post("/api/todos/{todo_id}/archive")
    async def todos_archive(todo_id: str):
        return _guarded(lambda: logbook.archive_todo(client(), todo_id))

    @app.post("/api/todos/reorder")
    async def todos_reorder(request: Request):
        body = await request.json()
        return _guarded(lambda: {"reordered": logbook.reorder_todos(client(), body["ids"])})

    @app.post("/api/todos/classify")
    async def todos_classify(request: Request):
        from . import classify
        body = await request.json()
        return _guarded(lambda: classify.classify_todo(
            client(), body.get("title", ""), body.get("given")).derived)

    # ---- Documents (the knowledge store the agent grounds on, docs/25) ----
    @app.get("/api/documents")
    def documents_list(kind: str | None = None, area: str | None = None,
                       company: str | None = None, contact: str | None = None):
        return _guarded(lambda: documents.feed(
            client(), kind=kind, area=area, company=company, contact=contact).derived)

    @app.get("/api/documents/{doc_id}")
    def documents_read(doc_id: str):
        return _guarded(lambda: documents.read(client(), doc_id))

    @app.post("/api/documents")
    async def documents_create(request: Request):
        body = await request.json()
        return _guarded(lambda: logbook.add_document(client(), **body))

    @app.patch("/api/documents/{doc_id}")
    async def documents_update(doc_id: str, request: Request):
        changes = await request.json()
        return _guarded(lambda: logbook.update_document(client(), doc_id, changes))

    @app.post("/api/documents/classify")
    async def documents_classify(request: Request):
        from . import classify
        body = await request.json()
        return _guarded(lambda: classify.classify_document(
            client(), body.get("title", ""), body.get("given")).derived)

    @app.post("/api/documents/context")
    async def documents_context(request: Request):
        from . import classify
        body = await request.json()
        return _guarded(lambda: classify.document_context(
            client(), body.get("title", ""), body.get("company")).derived)

    @app.delete("/api/documents/{doc_id}")
    def documents_delete(doc_id: str):
        return _guarded(lambda: logbook.delete_document(client(), doc_id))

    # ---- Users & assignments (the small team, docs/27) ----
    def current_user(request: Request) -> dict | None:
        # Entra Easy Auth authenticates in front of the app and passes the
        # signed-in email as a header. SECURITY (docs/27): an authenticated
        # identity that is NOT in the users table is never silently promoted —
        # only a mapped user, or the exact configured operator email (for
        # bootstrap/recovery), gets a role; anything else is a guest and
        # role_guard then 403s every admin/destructive action. A header-less
        # request assumes the operator ONLY on a local instance (dev) — in prod a
        # header-less request is off-proxy/unauthenticated and gets no role.
        from . import users as users_mod
        from .config import is_local_instance
        c = client()
        op = (config.operator_email or "").strip().lower()
        email = (request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME") or "").strip().lower()
        _operator = {"user_id": None, "name": op or "operator", "email": op,
                     "role": "operator", "active": True}
        if email:
            user = users_mod.resolve(c, email)
            if user:
                return user
            if op and email == op:      # the configured operator, even pre-seeding
                return _operator
            return None                 # authenticated but unmapped → guest
        if op and is_local_instance(config.instance_url):
            return users_mod.resolve(c, op) or _operator
        return None

    @app.get("/api/me")
    def me_route(request: Request):
        # `as_of` rides along with identity because the UI must SAY when this
        # instance reckons from a date other than today (clock.py). Null here
        # is the normal case and means the real clock.
        def go():
            who = current_user(request) or {"role": "guest", "name": "Guest"}
            reckoning = clock.reckoning()
            return {**who, "as_of": reckoning.isoformat() if reckoning else None}
        return _guarded(go)

    # Role enforcement (docs/27 Phase 2): an SDR gets read + safe writes; the
    # operator-only operations are destructive (delete/remove) and admin (users,
    # routine definitions, index rebuild). One central, auditable policy — a
    # missed per-endpoint guard can't open a hole.
    _OPERATOR_ONLY = [
        ("DELETE", re.compile(r"^/api/(documents|tokens)/")),
        ("POST", re.compile(r"^/api/(users|routines|tokens)$")),
        ("PATCH", re.compile(r"^/api/(users|routines)/")),
        # listing tokens is admin; the raw Data sheets expose whole tables (incl.
        # user PII) so they're operator-only too.
        ("GET", re.compile(r"^/api/(tokens|tables?)$")),
        ("POST", re.compile(r"^/api/(search/reindex)$")),
    ]

    @app.middleware("http")
    async def role_guard(request: Request, call_next):
        method, path = request.method, request.url.path
        if any(m == method and rx.match(path) for m, rx in _OPERATOR_ONLY):
            try:
                role = (current_user(request) or {}).get("role")
            except Exception:
                role = None
            if role != "operator":
                return JSONResponse(
                    {"error": "operator only — this action is restricted to the operator role"},
                    status_code=403)
        return await call_next(request)

    @app.get("/api/users")
    def users_route():
        from . import users as users_mod
        return _guarded(lambda: {"users": users_mod.list_users(client(), active_only=False)})

    @app.post("/api/users")
    async def users_create(request: Request):
        body = await request.json()
        return _guarded(lambda: logbook.add_user(client(), **body))

    @app.patch("/api/users/{user_id}")
    async def users_update(user_id: str, request: Request):
        changes = await request.json()
        return _guarded(lambda: logbook.update_user(client(), user_id, changes))

    @app.get("/api/assignments")
    def assignments_list(entity: str | None = None):
        # a flat map "entity:entity_id" -> user_id, so a list view can render the
        # owner per row without a per-row fetch.
        from . import users as users_mod
        return _guarded(lambda: {"map": {
            f"{e}:{i}": u for (e, i), u in users_mod.assignment_map(client(), entity).items()}})

    @app.post("/api/assignments")
    async def assignments_set(request: Request):
        body = await request.json()
        return _guarded(lambda: logbook.set_assignment(
            client(), body["entity"], body["entity_id"], body.get("user_id")))

    @app.get("/api/my-work")
    def my_work_route(request: Request):
        from . import users as users_mod
        def go():
            user = current_user(request)
            if not user:
                return {"user_id": None, "count": 0, "contacts": [], "todos": [], "deals": []}
            return users_mod.my_work(client(), user["user_id"]).derived
        return _guarded(go)

    # ---- API tokens for the remote MCP (docs/28) — operator-only (role_guard) ----
    @app.get("/api/tokens")
    def tokens_list():
        from . import tokens as tokens_mod
        return _guarded(lambda: {"tokens": tokens_mod.list_tokens(client())})

    @app.post("/api/tokens")
    async def tokens_create(request: Request):
        body = await request.json()
        # returns the plaintext ONCE — the client must show + let the operator copy
        # it now; it is never stored and cannot be retrieved again.
        return _guarded(lambda: logbook.add_token(client(), body["label"]))

    @app.delete("/api/tokens/{token_id}")
    def tokens_revoke(token_id: str):
        return _guarded(lambda: logbook.revoke_token(client(), token_id))

    # ---- Data sheets (raw rows of any table, incl. old/closed cases) ----
    @app.get("/api/tables")
    def tables_route():
        return _guarded(lambda: {"tables": sheets.list_tables(client())})

    @app.get("/api/table")
    def table_route(name: str = "deals", limit: int = sheets.SHEET_LIMIT,
                    where: str | None = None):
        scope = json.loads(where) if where else None
        return _guarded(lambda: sheets.table_sheet(client(), name, limit, scope))

    # ---- Deals (pipeline + close-likelihood) ----
    @app.get("/api/deals")
    def deals_route():
        # fast: aggregates + stalled flags, no per-deal predict. The dashboard
        # resolves each deal's close-likelihood lazily via /api/pwin.
        return _guarded(lambda: deals.pipeline(client(), predict=False).derived)

    @app.get("/api/pwin")
    def pwin_route(stage: str, blocker: str, champion_present: str, segment: str | None = None):
        # Aito's P(won) for one deal profile — cached per profile in the browser.
        return _guarded(lambda: deals.close_likelihood(
            client(), stage, blocker, champion_present, segment=segment))

    @app.get("/api/who-to-reach")
    def who_to_reach_route():
        # fast: stalled deals + their contacts, no predict — the dashboard fills
        # p_win in lazily (shared /api/pwin cache) and ranks client-side.
        return _guarded(lambda: deals.who_to_reach(client(), predict=False).derived)

    @app.get("/api/sales-trend")
    def sales_trend_route():
        from . import saleskpi
        return _guarded(lambda: saleskpi.win_trend(client()))

    @app.get("/api/graph")
    def graph_route():
        # the knowledge graph board: one Aito query per question, each returned
        # with the query that answered it (docs/31).
        from . import graph
        return _guarded(lambda: graph.board(client()))

    # ---- Companies (contacts rolled up by company, joined to deals) ----
    @app.get("/api/companies")
    def companies_route():
        from . import companies
        return _guarded(lambda: companies.roster(client()).derived)

    @app.get("/api/companies/{company_id}")
    def company_detail_route(company_id: str):
        from . import companies
        return _guarded(lambda: companies.detail(client(), company_id).derived)

    @app.post("/api/companies")
    async def companies_create(request: Request):
        """Create a company entity (the note editor's 'new company' button).
        Idempotent on the name slug, so it doubles as ensure-exists."""
        body = await request.json()
        return _guarded(lambda: logbook.add_company(client(), body["name"]))

    @app.post("/api/contacts")
    async def contacts_create(request: Request):
        """Add a person to the rolodex (the note editor's 'new person' button).
        Ensures the person's company entity exists first, so the new contact's
        company_id link never dangles."""
        body = await request.json()

        def create():
            company = body.get("company")
            if company:
                logbook.add_company(client(), company)   # ensure the link target
            row = logbook.add_contact(client(), **body)
            return {"id": row["contact_id"], "name": row["name"], "company": row["company"]}
        return _guarded(create)

    # ---- Smart search (unified index over content; Aito text-match ranking,
    # learned by clicks). Serving logs impressions server-side (docs/23, A+C). ----
    @app.get("/api/search")
    def search_route(q: str, kind: str | None = None, top_n: int = 10):
        from . import search, embed
        return _guarded(lambda: search.serve(
            client(), q, kind=kind, top_n=top_n, source="dashboard",
            embed=embed.embedder(config)))

    @app.get("/api/quickfind")
    def quickfind_route(q: str):
        from . import search
        return _guarded(lambda: search.quick_find(client(), q))

    @app.post("/api/search/click")
    async def search_click(request: Request):
        from . import search
        body = await request.json()
        return _guarded(lambda: search.record_click(
            client(), body["context_id"], body["item_id"]))

    @app.post("/api/search/reindex")
    def search_reindex():
        from . import search, embed
        return _guarded(lambda: search.build_index(client(), embed=embed.embedder(config)))

    # ---- Decisions (the dogfood scorecard) ----
    @app.get("/api/decisions")
    def decisions_route():
        return _guarded(lambda: decisions.scorecard(client()).derived)

    # ---- Experiments (the Build-Measure-Learn board) ----
    @app.get("/api/experiments")
    def experiments_route():
        return _guarded(lambda: experiments.board(client()).derived)

    # ---- Assistant conversations (stored in Aito; durable across devices) ----
    @app.get("/api/chats")
    def chats_list():
        from . import chats
        return _guarded(lambda: {"conversations": chats.list_chats(client())})

    @app.put("/api/chats/{cid}")
    async def chats_save(cid: str, request: Request):
        body = await request.json()
        from . import chats
        return _guarded(lambda: chats.save_chat(client(), cid, body.get("title"),
                                                body.get("msgs"), body.get("updated")))

    @app.delete("/api/chats/{cid}")
    def chats_delete(cid: str):
        from . import chats
        return _guarded(lambda: chats.remove_chat(client(), cid))

    # ---- Change log (audit of what was created / updated / done / won / lost) ----
    @app.get("/api/changelog")
    def changelog_route(limit: int = 100, entity: str = ""):
        from . import changelog
        return _guarded(lambda: changelog.recent(client(), limit=limit, entity=entity or None))

    # ---- Assistant (the right-side chat; bounded Aito-backed tool loop) ----
    @app.post("/api/assistant/chat")
    async def assistant_chat(request: Request):
        from . import assistant
        body = await request.json()
        history = body.get("messages", [])

        def go():
            turn = assistant.run_turn(history, client=client())
            return {"reply": turn.reply, "trace": turn.trace, "rounds": turn.rounds}
        return _guarded(go)

    # ---- Segment 360 ----
    @app.get("/api/dimensions")
    def dimensions():
        return {"dimensions": SEGMENT_DIMENSIONS, "values": SEGMENT_VALUES}

    @app.get("/api/360")
    def segment_360_route(segment: str = "", tier: str = "",
                          ai_lifecycle: str = "", source: str = ""):
        slice_ = {k: v for k, v in {
            "segment": segment, "tier": tier,
            "ai_lifecycle": ai_lifecycle, "source": source}.items() if v}
        return _guarded(lambda: segment_360(client(), slice_).derived)

    # ---- Funnels (slice dimensions vary per funnel, so read raw query) ----
    @app.get("/api/funnels")
    def funnel_catalog():
        return _guarded(lambda: {"funnels": [
            {"key": k, "label": f.label, "dimensions": f.dimensions,
             "values": funnels.dimension_values(client(), k)}
            for k, f in funnels.FUNNELS.items()
        ]})

    @app.get("/api/funnel")
    def funnel_route(request: Request, name: str = "website"):
        spec = funnels.FUNNELS.get(name)
        if spec is None:
            return JSONResponse({"error": f"unknown funnel {name!r}"}, status_code=404)
        q = request.query_params
        slice_ = {d: q[d] for d in spec.dimensions if q.get(d)}
        return _guarded(lambda: funnels.funnel(client(), name, slice_).derived)

    # ---- Post scorer ----
    @app.get("/api/score-options")
    def score_options():
        return {"options": SCORE_OPTIONS, "features": scorer.FEATURES}

    @app.get("/api/score")
    def score_route(request: Request, platform: str = ""):
        platform = platform or schema.default_platform()
        q = request.query_params
        feats = {f: q[f] for f in scorer.FEATURES if q.get(f)}
        return _guarded(lambda: scorer.score(client(), platform, feats).derived)

    # ---- Events to attend (the go/no-go board) ----
    @app.get("/api/events")
    def events_list():
        def go():
            rows = client().query({"from": "events", "limit": 100000})["hits"]
            rows.sort(key=lambda e: (e.get("starts", ""), e.get("event_id", "")))
            return {"events": rows}
        return _guarded(go)

    @app.post("/api/events")
    async def events_create(request: Request):
        body = await request.json()
        return _guarded(lambda: logbook.add_event(client(), **body))

    @app.post("/api/events/{event_id}/decide")
    async def events_decide(event_id: str, request: Request):
        body = await request.json()
        return _guarded(lambda: logbook.decide_event(client(), event_id, **body))

    # ---- Routines (recurring agentic tasks) ----
    @app.get("/api/routines")
    def routines_board():
        from . import routines
        return _guarded(lambda: routines.board(client()).derived)

    @app.post("/api/routines")
    async def routines_create(request: Request):
        body = await request.json()
        return _guarded(lambda: logbook.add_routine(client(), **body))

    @app.patch("/api/routines/{routine_id}")
    async def routines_update(routine_id: str, request: Request):
        changes = await request.json()
        return _guarded(lambda: logbook.update_routine(client(), routine_id, changes))

    @app.post("/api/routines/{routine_id}/tick")
    def routines_tick(routine_id: str):
        return _guarded(lambda: logbook.tick_routine(client(), routine_id))

    @app.post("/api/routines/{routine_id}/prepare")
    async def routines_prepare(routine_id: str, request: Request):
        from . import routines
        body = await request.json() if await request.body() else {}
        def go():
            c = client()
            match = [r for r in c.query({"from": "routines", "limit": 10000})["hits"]
                     if r["routine_id"] == routine_id]
            assert match, f"unknown routine_id {routine_id!r}"
            return routines.prepare(c, match[0]).derived
        return _guarded(go)

    @app.post("/api/routines/{routine_id}/run")
    def routines_run(routine_id: str):
        # Execute the routine now through the assistant loop (rule-1 fence):
        # narrate to a dated document + tick. force=True — an explicit click means run
        # it even if it isn't due. Uses the LLM, so it can take a few seconds.
        from . import routines
        return _guarded(lambda: routines.run_routine(client(), routine_id))

    # ---- Marketing write surface: materials, channels, posts (go/no-go) ----
    @app.post("/api/materials")
    async def materials_create(request: Request):
        body = await request.json()
        return _guarded(lambda: logbook.add_material(client(), **body))

    @app.post("/api/channels")
    async def channels_create(request: Request):
        body = await request.json()
        return _guarded(lambda: logbook.add_channel(client(), **body))

    @app.post("/api/posts")
    async def posts_create(request: Request):
        body = await request.json()
        return _guarded(lambda: logbook.add_post(client(), **body))

    @app.post("/api/posts/{post_id}/result")
    async def posts_result(post_id: str, request: Request):
        body = await request.json()
        return _guarded(lambda: logbook.log_post_result(client(), post_id, **body))

    # ---- liveness (container / load-balancer health probe). Deliberately does
    # NOT touch Aito: it answers whether the web process is up, not whether the
    # data layer is reachable (that's what `doctor` is for). ----
    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    # ---- the React app (vite build → web_dist). SPA: unknown non-/api paths
    # fall back to index.html so client-side routing works. ----
    # index.html must never be cached — it names the content-hashed JS/CSS, so a
    # stale cached index keeps a phone on an old bundle after a deploy. The
    # hashed assets under /assets are safe to cache forever (the hash changes
    # when they do).
    def _index() -> FileResponse:
        return FileResponse(WEB_DIST / "index.html", headers={"Cache-Control": "no-cache"})

    if WEB_DIST.exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/")
        def spa_root():
            return _index()

        @app.get("/{path:path}")
        def spa_fallback(path: str):
            if path.startswith("api/"):
                return JSONResponse({"error": "not found"}, 404)
            asset = WEB_DIST / path
            return FileResponse(asset) if asset.is_file() else _index()
    else:
        @app.get("/")
        def needs_build():
            return JSONResponse(
                {"error": "React app not built. Run: cd frontend && npm run build"}, 503)

    if remote_mcp is None:
        return app

    # Route the MCP-owned paths to the MCP handler ABOVE FastAPI's router — a
    # Mount would lose bare "/mcp" to the SPA catch-all (a POST there 405s before
    # the trailing-slash redirect), and the OAuth endpoints (/authorize, /token,
    # /register, /revoke, /.well-known/oauth-*) would likewise be swallowed by the
    # SPA. The dispatcher keeps FastAPI's lifespan (it runs the session manager)
    # by delegating every other scope, including lifespan, straight to the app.
    guarded, owned = remote_mcp[1], remote_mcp[2]

    def _is_mcp(path: str) -> bool:
        return any(path == p or path.startswith(p + "/") for p in owned)

    async def dispatch(scope, receive, send):
        if scope["type"] == "http" and _is_mcp(scope["path"]):
            return await guarded(scope, receive, send)
        return await app(scope, receive, send)

    return dispatch


def serve(config: Config, host: str = "127.0.0.1", port: int = 8770) -> None:
    import uvicorn
    print(f"aito-company-ai dashboard on http://{host}:{port}  (Ctrl-C to stop)")
    print(f"  Aito: {config.instance_url}  ·  API docs: http://{host}:{port}/api/docs")
    uvicorn.run(create_app(config), host=host, port=port, log_level="warning")
