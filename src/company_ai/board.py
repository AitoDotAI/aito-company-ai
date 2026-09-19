"""Run the advisory board and the week-prep inside the app.

The doctrine (docs/15, CLAUDE.md rule 1 amendment): the composition runs
server-side, but the reasoning is *grounded* — every fact comes from Aito
(the READS below, which are the same queries the dashboard and MCP use), and
the LLM only writes prose from those facts. No scoring or prediction happens
here; that is Aito's, always (rule 2).

Two seams kept clean for testing:
  - `gather()` collects the Aito facts — deterministic given `as_of`.
  - `assemble()` builds the (system, user) messages — pure given its inputs.
  - the LLM call is the only non-deterministic, external step, injected so a
    booktest can run the whole pipeline with a fake composer.
"""

import json
import sys
import threading
import tomllib
import traceback
from datetime import date, timedelta
from pathlib import Path

from . import analytics, changelog, deals, decisions, experiments, funnels, queries, schema, scorer, todos
from .aito import AitoClient
from .config import REPO_ROOT, Config
from .llm import make_client

PROMPTS = REPO_ROOT / "prompts"
# throwaway drafts from the board/week-prep composer (prepare mode) only —
# gitignored, real analysis never enters the repo. The advisory panel is NOT
# here anymore: it lives in Aito (schema.ADVISORY_REFLECTIONS), durable across
# restarts/devices, no container filesystem.
BRIEFS = REPO_ROOT / ".briefs"


def _funnels(client, as_of):
    return {key: funnels.funnel(client, key).derived for key in funnels.FUNNELS}


def _who(client, as_of):
    return {w: queries.who_to_call(client, w, top_n=5, as_of=as_of).derived
            for w in ("0800", "1215", "1600")}


def _todos_area(client, as_of):
    return {area: todos.pipeline(client, area, as_of=as_of).derived
            for area in ("sales", "distribution", "operations", "rnd")}


# advisor `reads` (board.toml) and the week-prep inputs both resolve through
# this registry: a read name -> a callable(client, as_of) -> JSON-able Aito
# facts. The predictive logic lives inside each call (in Aito), never here.
READS = {
    "deal_pipeline": lambda c, a: deals.pipeline(c, as_of=a).derived,
    "experiment_board": lambda c, a: experiments.board(c).derived,
    "decision_scorecard": lambda c, a: decisions.scorecard(c).derived,
    "segment_360": lambda c, a: analytics.segment_360(c).derived,
    "funnel": _funnels,
    "who_to_call": _who,
    "todos_now": lambda c, a: todos.now(c, as_of=a).derived,
    "todos_area": _todos_area,
    "score_post": lambda c, a: scorer.score(c, "linkedin").derived,
    "what_changed": lambda c, a: queries.what_changed(c, as_of=a).derived,
    "recent_changes": lambda c, a: changelog.recent(c, limit=50),
    # last week's activity only — the board's "review the week just gone" focus.
    # A 7-day window on the change log; advisors that read it reflect on what
    # actually moved in the last week rather than the standing snapshot.
    "last_week": lambda c, a: changelog.recent(
        c, limit=200, since=(a - timedelta(days=7)).isoformat()),
}


_DEFAULT_META = {"timezone": "Europe/Helsinki", "one_screen": True,
                 "commend_then_advise": True}


def _toml() -> dict:
    """board.toml (meta + default roster). If the file is absent — e.g. a
    packaging that didn't ship prompts/ — degrade to sane meta and an empty
    default roster rather than crashing, so the roster still reads from Aito."""
    try:
        return tomllib.loads((PROMPTS / "board.toml").read_text())
    except FileNotFoundError:
        return {"meta": _DEFAULT_META, "advisor": []}


def default_roster() -> list[dict]:
    """The advisors declared in prompts/board.toml — the seed and the fallback."""
    return _toml()["advisor"]


def advisor_to_row(advisor: dict, rank: int) -> dict:
    """A roster advisor -> an `advisors` table row (reads joined; rank for order)."""
    return {"advisor_id": advisor["key"], "name": advisor["name"],
            "persona": advisor.get("persona") or None, "mandate": advisor["mandate"],
            "reads": ",".join(advisor["reads"]), "rank": rank,
            "active": True, "created": date.today().isoformat()}


def _advisor_from_row(row: dict) -> dict:
    """An `advisors` table row -> the roster-advisor shape the composer uses."""
    return {"key": row["advisor_id"], "name": row["name"],
            "persona": (row.get("persona") or None), "mandate": row["mandate"],
            "reads": [s.strip() for s in (row.get("reads") or "").split(",") if s.strip()]}


def load_roster(client: AitoClient | None = None) -> tuple[dict, list[dict]]:
    """(meta, advisors). The advisors come from the Aito `advisors` table when
    it is populated (runtime-editable, no redeploy), else from board.toml (the
    default). meta always comes from board.toml. A missing table (an instance
    predating it) falls back cleanly — not a silent skip, an intended default."""
    meta = _toml()["meta"]
    if client is not None:
        try:
            rows = client.query({"from": "advisors", "limit": 1000})["hits"]
        except Exception:
            rows = []
        active = [r for r in rows if r.get("active", True)]
        if active:
            active.sort(key=lambda r: r.get("rank", 0))
            return meta, [_advisor_from_row(r) for r in active]
    return meta, default_roster()


def gather(client: AitoClient, read_names: list[str], as_of: date) -> dict:
    """The Aito facts for a set of reads. Deterministic given `as_of`. An
    unknown read name raises (never silently skipped — rule 3)."""
    facts = {}
    for name in read_names:
        assert name in READS, f"unknown read {name!r}; have {sorted(READS)}"
        facts[name] = READS[name](client, as_of)
    return facts


def assemble(prompt_name: str, mode: str, meta: dict, advisors: list[dict],
             facts: dict) -> tuple[str, str]:
    """Build (system, user) for the composer. Pure given its inputs."""
    prompt_text = (PROMPTS / prompt_name).read_text()
    system = (
        "You are the composer specified in the PROMPT below; follow it exactly. "
        "You may use ONLY the Aito facts supplied in this message — never invent "
        "or round a number, and prefer weak-and-honest to confident-and-"
        "fabricated. You do not rank, score, or predict; Aito already did, and "
        "its numbers are the only ones you may cite.\n\n=== PROMPT ===\n"
        + prompt_text)
    blocks = [f"MODE: {mode}", ""]
    if advisors:
        blocks.append("BOARD ROSTER (each advisor's mandate and the facts it leans on):")
        for a in advisors:
            blocks.append(f"- {a['name']} [{a['key']}]: {a['mandate']} "
                          f"(reads: {', '.join(a['reads'])})")
        blocks.append("")
    blocks.append("=== AITO FACTS ===")
    blocks.append(json.dumps(facts, indent=2, default=str, sort_keys=True))
    return system, "\n".join(blocks)


# which reads each composer needs. The board uses the union of its roster's
# declared reads; week-prep uses a fixed planning set.
def _board_reads(advisors: list[dict]) -> list[str]:
    seen = []
    for a in advisors:
        for r in a["reads"]:
            if r not in seen:
                seen.append(r)
    return seen


WEEK_PREP_READS = ["todos_now", "todos_area", "deal_pipeline", "experiment_board",
                   "funnel", "score_post", "what_changed"]

COMPOSERS = {
    "board-review.md": lambda advisors: _board_reads(advisors),
    "week-prep.md": lambda advisors: WEEK_PREP_READS,
}


def run(prompt_name: str, mode: str, *, client: AitoClient | None = None,
        llm=None, as_of: date | None = None, save: bool = True) -> dict:
    """Gather Aito facts, assemble the prompt, compose with the LLM. In
    `prepare` mode the draft is written to .briefs/ (gitignored)."""
    assert prompt_name in COMPOSERS, f"unknown composer {prompt_name!r}; have {sorted(COMPOSERS)}"
    config = Config.from_env()
    client = client or AitoClient(config.instance_url, config.api_key)
    as_of = as_of or date.today()
    meta, advisors = load_roster(client)
    roster = advisors if prompt_name == "board-review.md" else []
    facts = gather(client, COMPOSERS[prompt_name](advisors), as_of)
    system, user = assemble(prompt_name, mode, meta, roster, facts)
    llm = llm or make_client(config)
    text = llm.complete(system, user, max_tokens=COMPOSE_TOKENS)
    saved = None
    if save:
        # every run leaves an artifact so a scheduled (cron) run is readable;
        # the mode is in the name (prepare draft vs the live board/plan).
        BRIEFS.mkdir(parents=True, exist_ok=True)
        out = BRIEFS / f"{Path(prompt_name).stem}-{mode}-{as_of.isoformat()}.md"
        out.write_text(text)
        saved = str(out)
    return {"prompt": prompt_name, "mode": mode, "model": getattr(llm, "model", "?"),
            "text": text, "saved": saved}


# ── The advisory panel ────────────────────────────────────────────────────
# The Friday review (run/board-review.md) composes ONE synthesised document.
# The panel is the same doctrine turned into a *board*: each advisor speaks in
# its own voice, from its own reads, as a separate composition — so a persona
# ("Paul Graham") comes through. Still rule-1(a) writers: no tools, no actions,
# and every number is one Aito produced (rule 2). The Chair speaks last and
# synthesises the others. Surfaced in the dashboard's Advisory view (docs/15).

ADVISOR_RULES = (
    " Reflect on this one-person company from your focus in a few tight sentences "
    "(a short paragraph — one phone screen at most). Commend the real wins first, "
    "then name the single most important thing to change. You may cite ONLY the "
    "Aito facts given below — never invent or round a number, and prefer weak-and-"
    "honest to confident-and-fabricated. You do not rank, score, or predict; Aito "
    "already did, and its numbers are the only ones you may cite.")

# Generous even though a reflection is short: on a *reasoning* model (gpt-5*)
# the hidden reasoning tokens count against this budget, so a small cap (was
# 700) is eaten by reasoning and the model returns EMPTY content — an empty
# reflection column. Same lesson as the assistant's REPLY_TOKENS.
COMPOSE_TOKENS = 8192


def _reflection_text(raw: str, name: str) -> str:
    """The reflection, or — if the model returned empty (reasoning ate the
    budget) — a visible placeholder plus a loud console line, never a silent
    blank column."""
    text = (raw or "").strip()
    if not text:
        print(f"[advisory] {name}: model returned an EMPTY reflection "
              f"(likely reasoning consumed the {COMPOSE_TOKENS}-token budget)",
              file=sys.stderr, flush=True)
        return "(the model returned an empty reflection — try again)"
    return text

def _advisor_voice(advisor: dict) -> str:
    """The advisor's system persona. With `persona` set (e.g. a named figure),
    it speaks in that voice; otherwise it is the neutral role advisor."""
    persona = advisor.get("persona")
    if persona:
        return (f"You are {persona}, sitting as the '{advisor['name']}' advisor on the "
                f"board of a one-person company. Speak in that person's voice, values, "
                f"and characteristic advice.")
    return f"You are the '{advisor['name']}' advisor on the board of a one-person company."


def _advisor_user(advisor: dict, facts: dict, prior: list[dict] | None) -> str:
    """The advisor's user message: its mandate, the Chair's view of the others,
    and the Aito facts — the only numbers it may cite."""
    blocks = [f"YOUR MANDATE: {advisor['mandate']}", ""]
    if prior:
        blocks.append("THE OTHER ADVISORS SAID (synthesise them, don't just repeat):")
        for p in prior:
            blocks.append(f"- {p['name']}: {p['reflection']}")
        blocks.append("")
    blocks.append("=== AITO FACTS (the only numbers you may cite) ===")
    blocks.append(json.dumps(facts, indent=2, default=str, sort_keys=True))
    return "\n".join(blocks)


def panel(*, client: AitoClient | None = None, llm=None,
          as_of: date | None = None, save: bool = True) -> dict:
    """Run the advisory board: each roster advisor reflects in its own voice
    from its own reads; the Chair (last) synthesises the others. Grounded and
    tool-less (rule 1a). Saved to .briefs/ (gitignored — real analysis stays
    out of the repo) so the dashboard can show the latest without re-running."""
    config = Config.from_env()
    client = client or AitoClient(config.instance_url, config.api_key)
    as_of = as_of or date.today()
    meta, advisors = load_roster(client)
    llm = llm or make_client(config)
    reflections: list[dict] = []
    for advisor in advisors:
        facts = gather(client, advisor["reads"], as_of)
        prior = reflections if advisor["key"] == "chair" else None
        system = _advisor_voice(advisor) + ADVISOR_RULES
        text = llm.complete(system, _advisor_user(advisor, facts, prior), max_tokens=COMPOSE_TOKENS)
        reflections.append({"key": advisor["key"], "name": advisor["name"],
                            "persona": advisor.get("persona"), "reflection": _reflection_text(text, advisor["name"])})
    if save:
        for refl in reflections:
            _save_reflection(client, refl, as_of, getattr(llm, "model", "?"))
    return {"as_of": as_of.isoformat(), "model": getattr(llm, "model", "?"),
            "advisors": reflections}


_REFLECTION_COLUMNS = tuple(schema.ADVISORY_REFLECTIONS["columns"])


def _save_reflection(client: AitoClient, entry: dict, as_of: date, model: str) -> None:
    """Upsert one advisor's reflection into Aito (schema.ADVISORY_REFLECTIONS):
    replace this advisor's row. A per-advisor, one-at-a-time run persists as it
    goes; the dashboard joins reflections to the roster by key.

    Rewrites the whole (tiny) table rather than a predicate delete: the v2
    `_modify` delete removes the WRONG row on a migrated table, so
    `delete_entries({advisor_id})` was silently dropping a *different* advisor's
    reflection. Read all, drop this advisor's row, re-upload — reliable on any
    engine, and the reflect run is per-advisor and sequential so there is no
    concurrent writer to race."""
    client.ensure_table("advisory_reflections", schema.ADVISORY_REFLECTIONS)
    new_row = {
        "advisor_id": entry["key"], "name": entry["name"],
        "persona": entry.get("persona"), "reflection": entry["reflection"],
        "as_of": as_of.isoformat(), "model": model}
    existing = client.query({"from": "advisory_reflections", "limit": 10000})["hits"]
    kept = [{k: r.get(k) for k in _REFLECTION_COLUMNS}
            for r in existing if r.get("advisor_id") != entry["key"]]
    client.delete_table("advisory_reflections")
    client.create_table("advisory_reflections", schema.ADVISORY_REFLECTIONS)
    client.upload_batch("advisory_reflections", kept + [new_row])


def reflect(key: str, *, prior: list[dict] | None = None, client: AitoClient | None = None,
            llm=None, as_of: date | None = None, save: bool = True) -> dict:
    """Run ONE advisor's reflection (the dashboard drives the board one advisor
    at a time, so each HTTP request stays short — a full-panel run of 5 reasoning
    calls otherwise overruns the platform's request timeout). `prior` is the
    other advisors' reflections, used only by the chair to synthesise. Persists
    into Aito so history + other devices see it. Unknown key raises."""
    config = Config.from_env()
    client = client or AitoClient(config.instance_url, config.api_key)
    as_of = as_of or date.today()
    _, advisors = load_roster(client)
    advisor = next((a for a in advisors if a["key"] == key), None)
    assert advisor is not None, f"unknown advisor {key!r}; have {[a['key'] for a in advisors]}"
    llm = llm or make_client(config)
    facts = gather(client, advisor["reads"], as_of)
    use_prior = prior if advisor["key"] == "chair" else None
    system = _advisor_voice(advisor) + ADVISOR_RULES
    text = llm.complete(system, _advisor_user(advisor, facts, use_prior), max_tokens=COMPOSE_TOKENS)
    entry = {"key": advisor["key"], "name": advisor["name"],
             "persona": advisor.get("persona"), "reflection": _reflection_text(text, advisor["name"])}
    if save:
        _save_reflection(client, entry, as_of, getattr(llm, "model", "?"))
    return entry


def latest_panel(client: AitoClient | None = None) -> dict:
    """The cached advisory panel from Aito, or an empty shell if none has run.
    as_of is the newest reflection's date; the dashboard joins by advisor key."""
    config = Config.from_env()
    client = client or AitoClient(config.instance_url, config.api_key)
    client.ensure_table("advisory_reflections", schema.ADVISORY_REFLECTIONS)
    rows = client.query({"from": "advisory_reflections", "limit": 1000})["hits"]
    if not rows:
        return {"as_of": None, "advisors": []}
    advisors = [{"key": r["advisor_id"], "name": r["name"],
                 "persona": r.get("persona"), "reflection": r["reflection"]} for r in rows]
    return {"as_of": max(r["as_of"] for r in rows),
            "model": rows[0].get("model"), "advisors": advisors}
    return {"as_of": None, "advisors": []}


# A panel run happens in a background thread so the operator can trigger it,
# leave, and come back to a finished board (a full run is several slow reasoning
# calls — far past the platform's request timeout for a synchronous endpoint).
# Single-worker uvicorn (api.serve), so this in-process state is authoritative;
# the saved panel file is the durable result the dashboard polls.
_run_lock = threading.Lock()
_run_state: dict = {"generating": False, "pending": [], "error": None}


def run_status() -> dict:
    return {"generating": _run_state["generating"], "pending": list(_run_state["pending"]),
            "run_error": _run_state["error"]}


def _run_panel(*, client: AitoClient | None = None, llm=None, as_of: date | None = None) -> dict:
    """Reflect every advisor in order, saving each into the panel as it lands.
    Runs to completion regardless of the client (the dashboard triggers it and
    polls). Also the synchronous unit the background worker and tests call."""
    config = Config.from_env()
    client = client or AitoClient(config.instance_url, config.api_key)
    llm = llm or make_client(config)
    as_of = as_of or date.today()
    _, advisors = load_roster(client)
    _run_state["pending"] = [a["key"] for a in advisors]
    prior: list[dict] = []
    for advisor in advisors:
        entry = reflect(advisor["key"], prior=prior, client=client, llm=llm, as_of=as_of)
        if advisor["key"] != "chair":
            prior.append({"name": entry["name"], "reflection": entry["reflection"]})
        _run_state["pending"] = [k for k in _run_state["pending"] if k != advisor["key"]]
    return latest_panel(client)


def start_panel_run(as_of: date | None = None) -> dict:
    """Kick off a background panel run unless one is already going. Returns at
    once; the dashboard polls GET /api/advisory (generating + pending) for
    progress and the reflections as they land."""
    if not _run_lock.acquire(blocking=False):
        return {"started": False, "already_running": True}
    _run_state["generating"] = True
    _run_state["error"] = None

    def worker():
        try:
            _run_panel(as_of=as_of)
        except Exception as exc:                      # surface, don't lose it (rule 3)
            _run_state["error"] = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        finally:
            _run_state["generating"] = False
            _run_lock.release()

    threading.Thread(target=worker, daemon=True).start()
    return {"started": True}
