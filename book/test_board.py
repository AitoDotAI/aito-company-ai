"""Board composer gate: the server-side board / week-prep run.

The composition is grounded — gather() pulls Aito facts, assemble() builds the
prompt deterministically, and the LLM only writes. The real model is external
and non-deterministic, so here it is a fake composer: we snapshot the *inputs*
the LLM is handed (proving Aito grounding) and check the plumbing. The real
LLM is config-swappable (gpt-5-mini now, high-end later); its absence raises
loudly rather than failing silently.
"""

import json
from datetime import date

import booktest as bt

from company_ai import board, loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config
from dataclasses import replace

from company_ai.llm import AzureOpenAIClient, LLMError, OpenAICompatClient, make_client

AS_OF = date(2026, 6, 17)


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _load_all(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_touches(client, SEED_DIR)
    loaders.load_sessions(client, SEED_DIR)
    loaders.load_materials(client, SEED_DIR)
    loaders.load_channels(client, SEED_DIR)
    loaders.load_posts(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_todos(client, SEED_DIR)
    loaders.load_decisions(client, SEED_DIR)
    loaders.load_experiments(client, SEED_DIR)


class FakeLLM:
    """Records what it was handed, returns a fixed line. Stands in for the
    swappable real provider so the pipeline is testable without a key."""
    model = "fake-1"

    def __init__(self):
        self.seen = None

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        self.seen = {"system": system, "user": user}
        return "COMPOSED (fake)"


def test_board_review_is_grounded(t: bt.TestCaseRun) -> None:
    client = _client()
    _load_all(client)
    llm = FakeLLM()

    t.h1("Friday board review — composed from Aito facts")
    out = board.run("board-review.md", "board", client=client, llm=llm,
                    as_of=AS_OF, save=False)
    t.tln(f"prompt={out['prompt']} mode={out['mode']} model={out['model']} text={out['text']!r}")

    # the composer's system message carries the prompt; the user message carries
    # the roster and the Aito facts — and ONLY Aito facts.
    seen = llm.seen
    t.tln(f"system cites the prompt file contents: {'Friday board review' in seen['system']}")
    t.tln(f"system forbids inventing numbers: {'never invent' in seen['system']}")

    facts = json.loads(seen["user"].split("=== AITO FACTS ===\n", 1)[1])
    t.tln(f"reads gathered (the roster's union): {sorted(facts)}")
    t.tln("grounding samples (numbers Aito produced, the only ones allowed):")
    t.tln(f"  open_deals = {facts['deal_pipeline']['kpis']['open_deals']}")
    t.tln(f"  validated_learning_rate = "
          f"{round(facts['experiment_board']['validated_learning_rate'], 4)}")
    t.tln(f"  decision acceptance = {round(facts['decision_scorecard']['acceptance'], 4)}")
    roster_names = [ln for ln in seen["user"].splitlines() if ln.startswith("- ")]
    t.tln(f"roster advisors in the prompt: {len(roster_names)}")


def test_week_prep_uses_planning_reads(t: bt.TestCaseRun) -> None:
    client = _client()
    _load_all(client)
    llm = FakeLLM()

    t.h1("Sunday week-prep — the planning read set")
    board.run("week-prep.md", "plan", client=client, llm=llm, as_of=AS_OF, save=False)
    facts = json.loads(llm.seen["user"].split("=== AITO FACTS ===\n", 1)[1])
    t.tln(f"reads gathered: {sorted(facts)}")
    t.tln(f"no board roster injected for week-prep: {'BOARD ROSTER' not in llm.seen['user']}")
    t.tln(f"week's todos present: {'todos_now' in facts and 'todos_area' in facts}")


def test_unknown_composer_and_read_raise(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)

    t.h1("an unknown composer raises")
    try:
        board.run("quarterly-review.md", "board", client=client, llm=FakeLLM())
        raise RuntimeError("ran an unknown composer")
    except AssertionError as e:
        t.tln(str(e))

    t.h1("an unknown read raises")
    try:
        board.gather(client, ["deal_pipeline", "crystal_ball"], AS_OF)
        raise RuntimeError("gathered an unknown read")
    except AssertionError as e:
        t.tln(str(e))


def test_llm_provider_seam(t: bt.TestCaseRun) -> None:
    t.h1("the provider is config-swappable; a missing key raises loudly")
    config = Config.from_env()
    clientless = OpenAICompatClient(api_key="", model="gpt-5-mini")
    try:
        clientless.complete("s", "u")
        raise RuntimeError("composed with no api key")
    except LLMError as e:
        t.tln(str(e))

    t.h1("default provider resolves to an OpenAI-compatible client")
    built = make_client(config)
    t.tln(f"provider={config.llm_provider} -> {type(built).__name__} model={built.model}")

    t.h1("Azure OpenAI: deployment URL, api-key auth, missing key raises")
    azure = AzureOpenAIClient(
        api_key="", endpoint="https://swedencentral.api.cognitive.microsoft.com",
        deployment="gpt-5-mini", api_version="2024-08-01-preview", model="gpt-5-mini")
    t.tln(f"url: {azure.url}")
    try:
        azure.complete("s", "u")
        raise RuntimeError("composed with no Azure key")
    except LLMError as e:
        t.tln(str(e))

    t.h1("make_client routes the azure provider")
    azure_cfg = replace(config, llm_provider="azure",
                        llm_azure_endpoint="https://swedencentral.api.cognitive.microsoft.com",
                        llm_azure_deployment="gpt-5-mini",
                        llm_azure_api_version="2024-08-01-preview")
    routed = make_client(azure_cfg)
    t.tln(f"provider=azure -> {type(routed).__name__} url={routed.url}")


class PanelLLM:
    """Records every (system, user) it is handed and returns a distinct line
    per call, so the panel's per-advisor plumbing is inspectable."""
    model = "fake-panel"

    def __init__(self):
        self.calls = []

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        self.calls.append({"system": system, "user": user})
        return f"REFLECTION#{len(self.calls)}"


def test_advisory_panel_reflects_per_advisor_and_grounds(t: bt.TestCaseRun) -> None:
    client = _client()
    _load_all(client)
    llm = PanelLLM()

    t.h1("advisory panel — one grounded reflection per roster advisor")
    out = board.panel(client=client, llm=llm, as_of=AS_OF, save=False)
    keys = [a["key"] for a in out["advisors"]]
    t.tln(f"advisors: {keys}")
    t.tln(f"one llm call per advisor: {len(llm.calls) == len(out['advisors'])}")
    # each advisor got its own grounded user message (only Aito facts)
    for call in llm.calls:
        assert "=== AITO FACTS" in call["user"]
    t.tln("every advisor was handed Aito facts (grounding), never free rein")

    t.h1("the chair speaks last and synthesises the others")
    chair = llm.calls[-1]
    t.tln(f"chair sees the others: {'THE OTHER ADVISORS SAID' in chair['user']}")
    t.tln(f"chair's message quotes an earlier reflection: {'REFLECTION#1' in chair['user']}")
    assert keys[-1] == "chair" and "REFLECTION#1" in chair["user"]

    t.h1("a persona voices that advisor (configured in board.toml)")
    learning = next(a for a in out["advisors"] if a["key"] == "learning")
    t.tln(f"learning persona: {learning['persona'].split(' — ')[0]}")
    learning_sys = llm.calls[keys.index("learning")]["system"]
    t.tln(f"learning's system speaks as its persona: "
          f"{learning['persona'].split(' — ')[0] in learning_sys}")


def _clear_reflections(client) -> None:
    from company_ai import schema
    client.delete_table("advisory_reflections")
    client.create_table("advisory_reflections", schema.ADVISORY_REFLECTIONS)


def test_advisory_reflect_one_at_a_time(t: bt.TestCaseRun) -> None:
    client = _client()
    _load_all(client)
    llm = PanelLLM()

    t.h1("reflect runs a single advisor (the dashboard loops, one short call each)")
    gtm = board.reflect("gtm", client=client, llm=llm, as_of=AS_OF, save=False)
    t.tln(f"gtm -> key={gtm['key']} reflection={gtm['reflection']}")
    t.tln(f"that call was NOT given prior advisors: "
          f"{'THE OTHER ADVISORS SAID' not in llm.calls[-1]['user']}")

    t.h1("the chair (last) is handed the prior reflections to synthesise")
    prior = [{"name": gtm["name"], "reflection": gtm["reflection"]}]
    board.reflect("chair", prior=prior, client=client, llm=llm, as_of=AS_OF, save=False)
    t.tln(f"chair sees prior: {'THE OTHER ADVISORS SAID' in llm.calls[-1]['user']}")
    assert "THE OTHER ADVISORS SAID" in llm.calls[-1]["user"]

    t.h1("saving one at a time accumulates into the panel (in Aito)")
    _clear_reflections(client)
    board.reflect("gtm", client=client, llm=llm, as_of=AS_OF)
    board.reflect("chair", prior=prior, client=client, llm=llm, as_of=AS_OF)
    saved = board.latest_panel(client)
    t.tln(f"saved panel keys: {sorted(a['key'] for a in saved['advisors'])} as_of={saved['as_of']}")
    assert {a["key"] for a in saved["advisors"]} == {"gtm", "chair"}

    t.h1("an unknown advisor raises (rule 3)")
    try:
        board.reflect("nope", client=client, llm=llm, as_of=AS_OF, save=False)
        raise RuntimeError("ran an unknown advisor")
    except AssertionError as e:
        t.tln(f"unknown -> {e}")


def test_advisory_background_run_reflects_all(t: bt.TestCaseRun) -> None:
    client = _client()
    _load_all(client)
    _clear_reflections(client)
    llm = PanelLLM()
    t.h1("the background run reflects every advisor, saving the panel as it goes")
    out = board._run_panel(client=client, llm=llm, as_of=AS_OF)
    t.tln(f"panel keys: {sorted(a['key'] for a in out['advisors'])}")
    t.tln(f"status after run: {board.run_status()}")
    assert {a["key"] for a in out["advisors"]} == \
        {"gtm", "marketing", "product", "learning", "chair"}
    assert board.run_status()["pending"] == []


def test_advisor_persona_voices_the_system(t: bt.TestCaseRun) -> None:
    t.h1("persona swaps the advisor's voice; no persona = the neutral role")
    plain = board._advisor_voice({"key": "x", "name": "Learning", "reads": []})
    voiced = board._advisor_voice(
        {"key": "x", "name": "Learning", "persona": "Paul Graham — make something people want", "reads": []})
    t.tln(f"neutral: {plain}")
    t.tln(f"voiced:  {voiced}")
    assert "Paul Graham" in voiced and "Paul Graham" not in plain


def test_advisory_roster_is_editable_in_aito(t: bt.TestCaseRun) -> None:
    from company_ai import log
    client = _client()
    loaders.create_schema(client)

    t.h1("no table populated yet → the roster falls back to board.toml")
    _, default = board.load_roster(client)
    t.tln(f"default (from board.toml): {[a['key'] for a in default]}")

    t.h1("seed the roster into Aito; it reads back from the table")
    n = loaders.load_advisors(client, None)
    _, seeded = board.load_roster(client)
    t.tln(f"seeded {n}; from Aito: {[a['key'] for a in seeded]}")

    t.h1("add an advisor (the write MCP + the dashboard both make)")
    log.add_advisor(client, "finance", "Finance / Runway",
                    "Watch burn and the runway of cash.", ["deal_pipeline"],
                    persona="Bill Gurley — durable unit economics")
    _, added = board.load_roster(client)
    t.tln(f"after add: {[a['key'] for a in added]}")
    t.tln(f"finance persona: {next(a for a in added if a['key']=='finance')['persona'].split(' — ')[0]}")

    t.h1("retune its reads, then remove it")
    log.update_advisor(client, "finance", {"reads": ["deal_pipeline", "funnel"]})
    _, edited = board.load_roster(client)
    t.tln(f"finance reads: {next(a for a in edited if a['key']=='finance')['reads']}")
    t.tln(f"remove: {log.remove_advisor(client, 'finance')}")
    _, removed = board.load_roster(client)
    t.tln(f"after remove: {[a['key'] for a in removed]}")

    t.h1("guards: an unknown read and a duplicate id raise (rule 3)")
    try:
        log.add_advisor(client, "x", "X", "m", ["crystal_ball"])
        raise RuntimeError("added an unknown read")
    except AssertionError as e:
        t.tln(f"unknown read -> {e}")
    try:
        log.add_advisor(client, "gtm", "dup", "m", ["deal_pipeline"])
        raise RuntimeError("added a duplicate id")
    except AssertionError as e:
        t.tln(f"duplicate id -> {e}")


def test_roster_survives_a_missing_board_toml(t: bt.TestCaseRun) -> None:
    # a packaging that didn't ship prompts/ must not crash the roster read —
    # meta degrades to defaults and the roster still comes from Aito.
    client = _client()
    loaders.create_schema(client)
    loaders.load_advisors(client)
    orig = board.PROMPTS
    try:
        board.PROMPTS = board.REPO_ROOT / "prompts-does-not-exist"
        t.h1("board.toml absent → default meta, roster still from Aito")
        meta, adv = board.load_roster(client)
        t.tln(f"meta timezone (default): {meta['timezone']}")
        t.tln(f"roster from Aito: {[a['key'] for a in adv]}")
        t.tln(f"default_roster with no file: {board.default_roster()}")
        assert {a["key"] for a in adv} == {"gtm", "marketing", "product", "learning", "chair"}
        assert board.default_roster() == []
    finally:
        board.PROMPTS = orig


def test_advisory_roster_seeds_on_first_edit(t: bt.TestCaseRun) -> None:
    from company_ai import log
    client = _client()
    loaders.create_schema(client)   # advisors table exists but empty

    t.h1("editing before an explicit seed materialises the default roster first")
    # so an edit never silently drops the other advisors it didn't mention
    log.update_advisor(client, "chair", {"persona": "Marc Andreessen — software eats the world"})
    _, adv = board.load_roster(client)
    t.tln(f"roster after seed-on-edit: {[a['key'] for a in adv]}")
    t.tln(f"chair persona now: {next(a for a in adv if a['key']=='chair')['persona'].split(' — ')[0]}")
    assert {a["key"] for a in adv} == {"gtm", "marketing", "product", "learning", "chair"}
