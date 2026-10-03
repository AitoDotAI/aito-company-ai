"""Run the week-prep composer inside the app.

The doctrine (CLAUDE.md rule 1 amendment): the composition runs server-side,
but the reasoning is *grounded* — every fact comes from Aito (the READS below,
the same queries the dashboard and MCP use), and the LLM only writes prose from
those facts. No scoring or prediction happens here; that is Aito's, always
(rule 2).

Two seams kept clean for testing:
  - `gather()` collects the Aito facts — deterministic given `as_of`.
  - `assemble()` builds the (system, user) messages — pure given its inputs.
  - the LLM call is the only non-deterministic, external step, injected so a
    booktest can run the whole pipeline with a fake composer.
"""

import json
from datetime import date, timedelta
from pathlib import Path

from . import clock
from . import (analytics, changelog, deals, decisions, experiments, funnels, queries,
               schema, scorer, todos)
from .aito import AitoClient
from .config import REPO_ROOT, Config
from .llm import make_client

PROMPTS = REPO_ROOT / "prompts"
# throwaway drafts from the week-prep composer (prepare mode) only — gitignored,
# real analysis never enters the repo.
BRIEFS = REPO_ROOT / ".briefs"


def _funnels(client, as_of):
    return {key: funnels.funnel(client, key).derived for key in funnels.FUNNELS}


def _who(client, as_of):
    return {w: queries.who_to_call(client, w, top_n=5, as_of=as_of).derived
            for w in ("0800", "1215", "1600")}


# experiments has its own read (experiment_board), so week prep takes the lanes.
WEEK_PREP_AREAS = tuple(a for a in schema.TODO_AREA_ORDER if a != "experiments")


def _todos_area(client, as_of):
    return {area: todos.pipeline(client, area, as_of=as_of).derived
            for area in WEEK_PREP_AREAS}


# a read name -> a callable(client, as_of) -> JSON-able Aito facts. The
# predictive logic lives inside each call (in Aito), never here.
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
    "last_week": lambda c, a: changelog.recent(
        c, limit=200, since=(a - timedelta(days=7)).isoformat()),
}


def gather(client: AitoClient, read_names: list[str], as_of: date) -> dict:
    """The Aito facts for a set of reads. Deterministic given `as_of`. An
    unknown read name raises (never silently skipped — rule 3)."""
    facts = {}
    for name in read_names:
        assert name in READS, f"unknown read {name!r}; have {sorted(READS)}"
        facts[name] = READS[name](client, as_of)
    return facts


def assemble(prompt_name: str, mode: str, facts: dict) -> tuple[str, str]:
    """Build (system, user) for the composer. Pure given its inputs."""
    prompt_text = (PROMPTS / prompt_name).read_text()
    system = (
        "You are the composer specified in the PROMPT below; follow it exactly. "
        "You may use ONLY the Aito facts supplied in this message — never invent "
        "or round a number, and prefer weak-and-honest to confident-and-"
        "fabricated. You do not rank, score, or predict; Aito already did, and "
        "its numbers are the only ones you may cite.\n\n=== PROMPT ===\n"
        + prompt_text)
    user = "\n".join([f"MODE: {mode}", "", "=== AITO FACTS ===",
                      json.dumps(facts, indent=2, default=str, sort_keys=True)])
    return system, user


WEEK_PREP_READS = ["todos_now", "todos_area", "deal_pipeline", "experiment_board",
                   "funnel", "score_post", "what_changed"]

COMPOSERS = {
    "week-prep.md": WEEK_PREP_READS,
}

# Generous cap: on a reasoning model the hidden reasoning tokens count against
# the budget, so a small cap is eaten by reasoning and the model returns EMPTY.
COMPOSE_TOKENS = 8192


def run(prompt_name: str, mode: str, *, client: AitoClient | None = None,
        llm=None, as_of: date | None = None, save: bool = True) -> dict:
    """Gather Aito facts, assemble the prompt, compose with the LLM. In
    `prepare` mode the draft is written to .briefs/ (gitignored)."""
    assert prompt_name in COMPOSERS, f"unknown composer {prompt_name!r}; have {sorted(COMPOSERS)}"
    config = Config.from_env()
    client = client or AitoClient(config.instance_url, config.api_key)
    as_of = as_of or clock.today()
    facts = gather(client, COMPOSERS[prompt_name], as_of)
    system, user = assemble(prompt_name, mode, facts)
    llm = llm or make_client(config)
    text = llm.complete(system, user, max_tokens=COMPOSE_TOKENS)
    saved = None
    if save:
        # every run leaves an artifact so a scheduled (cron) run is readable;
        # the mode is in the name (prepare draft vs the live plan).
        BRIEFS.mkdir(parents=True, exist_ok=True)
        out = BRIEFS / f"{Path(prompt_name).stem}-{mode}-{as_of.isoformat()}.md"
        out.write_text(text)
        saved = str(out)
    return {"prompt": prompt_name, "mode": mode, "model": getattr(llm, "model", "?"),
            "text": text, "saved": saved}
