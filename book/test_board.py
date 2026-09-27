"""Week-prep composer gate: the server-side week-prep run.

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


def test_week_prep_uses_planning_reads(t: bt.TestCaseRun) -> None:
    client = _client()
    _load_all(client)
    llm = FakeLLM()

    t.h1("Sunday week-prep — composed from the planning read set")
    out = board.run("week-prep.md", "plan", client=client, llm=llm, as_of=AS_OF, save=False)
    t.tln(f"prompt={out['prompt']} mode={out['mode']} model={out['model']} text={out['text']!r}")

    # the composer's system message carries the prompt; the user message carries
    # ONLY Aito facts.
    seen = llm.seen
    t.tln(f"system forbids inventing numbers: {'never invent' in seen['system']}")

    facts = json.loads(seen["user"].split("=== AITO FACTS ===\n", 1)[1])
    t.tln(f"reads gathered: {sorted(facts)}")
    t.tln("grounding samples (numbers Aito produced, the only ones allowed):")
    t.tln(f"  open_deals = {facts['deal_pipeline']['kpis']['open_deals']}")
    t.tln(f"  validated_learning_rate = "
          f"{round(facts['experiment_board']['validated_learning_rate'], 4)}")
    t.tln(f"week's todos present: {'todos_now' in facts and 'todos_area' in facts}")


def test_unknown_composer_and_read_raise(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)

    t.h1("an unknown composer raises")
    try:
        board.run("quarterly-review.md", "plan", client=client, llm=FakeLLM())
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

    t.h1("the provider selects the client — both ways, from explicit config")
    # NOT from the ambient environment. This printed whatever the developer
    # happened to have configured, so it read "openai" only while nobody had
    # Azure credentials in their test dotenv — and flipped to "azure" the day
    # someone did, with no code change. The seam is what is under test, so give
    # it both inputs explicitly.
    from dataclasses import replace
    as_openai = replace(config, llm_provider="openai", llm_azure_endpoint="")
    as_azure = replace(config, llm_provider="azure",
                       llm_azure_endpoint="https://example.api.cognitive.microsoft.com",
                       llm_azure_deployment="gpt-5-mini")
    for cfg in (as_openai, as_azure):
        built = make_client(cfg)
        t.tln(f"provider={cfg.llm_provider} -> {type(built).__name__} model={built.model}")

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
