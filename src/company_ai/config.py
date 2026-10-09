"""Environment-driven configuration. See .env.example for the contract."""

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "data" / "seed"
SEED_TINY_DIR = REPO_ROOT / "data" / "seed_tiny"

DEFAULT_EMBED_MODEL = "text-embedding-3-large"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", ""}


def _env_first(*names: str, default: str = "") -> str:
    """First non-empty value among env var names — lets clean COMPANY_AI_LLM_*
    names override, but fall back to vars the operator already has set."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def is_local_instance(instance_url: str) -> bool:
    """True only for a local Aito (localhost/127.0.0.1). Used to refuse
    seeding synthetic data into a remote/hosted instance without --force:
    synthetic-into-real is the dangerous direction (see docs/06-privacy.md)."""
    return urlparse(instance_url).hostname in _LOCAL_HOSTS


#: Hosts a public demo must never read: the internal ops instance holds the real
#: CRM. The demo reads a shared-demo database with synthetic data only.
PUBLIC_DEMO_DENIED_HOSTS = {"internal.aito.ai"}


def assert_public_demo_target(instance_url: str) -> None:
    """Refuse to serve a public demo from a denied host (docs/33-public-demo.md).
    A mis-pointed secret must stop the app loudly, not publish the real CRM."""
    host = urlparse(instance_url).hostname or ""
    assert host not in PUBLIC_DEMO_DENIED_HOSTS, (
        f"COMPANY_AI_PUBLIC_DEMO is set but AITO_INSTANCE_URL points at {host!r}, "
        "the internal ops instance. A public demo reads the shared-demo database only.")


def _public_demo_posture(config: "Config") -> "Config":
    """A public demo's billable and outbound features are OFF unless opted in.

    Clearing env vars cannot do this: _env_first skips empty values and falls
    back to the next name, and the unified demos container hands EVERY program
    every secret (the grocery demo's REACT_APP_OPENAI_* included). So a public
    demo would inherit a live, billable LLM key it never asked for. Instead the
    posture is decided here: no LLM, no embeddings, no web search or fetch, no
    MCP, whatever the environment carries. COMPANY_AI_PUBLIC_DEMO_LLM=1 turns
    the LLM back on deliberately (docs/33-public-demo.md lists what that needs).
    """
    if not config.public_demo:
        return config
    llm_opt_in = _env_first("COMPANY_AI_PUBLIC_DEMO_LLM").strip().lower() in ("1", "true", "yes")
    import dataclasses
    return dataclasses.replace(
        config,
        llm_api_key=config.llm_api_key if llm_opt_in else "",
        embed_api_key="",
        search_api_key="",
        fetch_enabled=False,
        mcp_token="",
    )


def instance_host(instance_url: str) -> str:
    """A short, legible label for an instance — host[/db] — to echo before
    any write so the target is never silent."""
    p = urlparse(instance_url)
    return f"{p.hostname or instance_url}{p.path}".rstrip("/") or instance_url


def _parse_as_of(raw: str) -> "date | None":
    """COMPANY_AI_AS_OF as an ISO date, or None for the real clock. A value
    that is set but unparseable RAISES rather than silently falling back to
    today: a demo reckoning from the wrong date looks like working software."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as e:
        raise AssertionError(
            f"COMPANY_AI_AS_OF={raw!r} is not an ISO date (YYYY-MM-DD)") from e


@dataclass(frozen=True)
class Config:
    instance_url: str
    api_key: str
    data_dir: Path | None
    library_dir: Path
    port: int
    # the week-prep composer's LLM (see src/company_ai/llm.py). Abstracted
    # behind a provider so gpt-5-mini-for-testing can become a high-end model
    # later by changing env only. The LLM composes prose from Aito's outputs; it
    # never scores or predicts — that stays in Aito (CLAUDE.md rule 2).
    llm_provider: str
    llm_model: str
    llm_api_key: str
    llm_base_url: str
    # Azure OpenAI (deployment-addressed, api-key auth). Mapped from the
    # operator's existing REACT_APP_OPENAI_* vars when present, so no
    # duplication — only the key needs adding.
    llm_azure_endpoint: str
    llm_azure_deployment: str
    llm_azure_api_version: str
    # the assistant's one non-Aito tool: web search (see src/company_ai/
    # websearch.py, docs/16). Off unless a key is present, and swappable by env
    # alone. The model narrates results; it never scores or predicts (rule 2).
    search_provider: str
    search_api_key: str
    search_endpoint: str
    # the assistant's second non-Aito read: fetch a web page by URL
    # (src/company_ai/webfetch.py, docs/16). Keyless, on by default; set
    # COMPANY_AI_WEB_FETCH=off to disable server-side page fetching.
    fetch_enabled: bool
    # optional allowlist curating the assistant's tool registry (docs/16). Empty
    # = every available tool; else only these names are exposed to the model.
    assistant_tools: list[str]
    # the bearer token gating the remote MCP endpoint at /mcp (docs/26). Empty =
    # remote MCP disabled entirely (fail closed — the /mcp route isn't mounted).
    # Set a strong random secret in prod; cloud Claude sends it as
    # `Authorization: Bearer <token>`.
    mcp_token: str
    # the operator's email (docs/27), used to resolve identity when Entra Easy
    # Auth passes no header (local dev, or a direct API hit) — falls back to this
    # user. Empty = fall back to the first operator in the users table.
    operator_email: str
    # The date this instance RECKONS FROM — overdue-ness, cold deals, routine
    # due-state. Empty (the default) = the real clock, which is what any live
    # instance wants. Set it only for a fixed demo dataset, whose dates would
    # otherwise rot until every deal reads as stalled and the Now view's
    # ranking means nothing. It never moves data and never touches write
    # stamps (created/ts/last_done stay real time, so the audit trail is
    # honest); it only changes what "now" the READS compare against. Whenever
    # it is set the UI says so, because an instance quietly reckoning from a
    # date that is not today is the dishonest version of this.
    as_of: date | None
    # the public HTTPS origin the app is reached at (e.g. https://ai.example.com),
    # used as the OAuth issuer/resource base for the remote MCP connector
    # (docs/29). Empty = derive from the request at mount time isn't possible, so
    # OAuth stays off and /mcp accepts only bearer tokens (docs/28). Set it in
    # prod; for local testing point it at the uvicorn origin (http allowed).
    public_url: str
    # Azure OpenAI embeddings for semantic/cross-lingual smart search (docs/23).
    # Its own deployment (and often its own region/endpoint) separate from the
    # chat model; the api-key defaults to the LLM key when the resource is shared.
    # Empty endpoint/deployment ⇒ embeddings off ⇒ search stays pure text-match
    # (graceful degrade). Vectors are a load-time featurization; Aito owns the
    # ranking ($vectorSimilarity/$nearest), so rule 2 is intact.
    embed_endpoint: str
    embed_deployment: str
    embed_api_version: str
    embed_api_key: str
    embed_model: str = ""
    # COMPANY_AI_PUBLIC_DEMO: anonymous visitors on a public host. Read-only
    # (every non-GET /api/* is refused), no write side effects on reads, and the
    # internal host is refused at startup. See docs/33-public-demo.md.
    public_demo: bool = False

    @property
    def embed_target(self) -> str:
        """The model to ask for — an Azure deployment name or an OpenAI model.

        Defaulted, because `text-embedding-3-large` is what both sides use and
        naming it twice is just another thing to get wrong. What is NOT
        defaulted is the provider signal (an endpoint, or an explicit model):
        the key already falls back to the LLM key, so a default on both would
        turn embeddings — and billing — on for anyone who merely has a key."""
        named = self.embed_deployment if self.embed_is_azure else self.embed_model
        return named or DEFAULT_EMBED_MODEL

    @property
    def embed_is_azure(self) -> bool:
        """Azure OpenAI (endpoint + deployment + `api-key` header) rather than
        OpenAI proper. An Azure resource is any endpoint that is not
        api.openai.com; naming a MODEL instead of a deployment selects OpenAI."""
        if self.embed_model and not self.embed_deployment:
            return False
        return bool(self.embed_endpoint) and "api.openai.com" not in self.embed_endpoint

    @property
    def embed_enabled(self) -> bool:
        """Semantic search needs a key plus enough to address a model.

        Azure wants an endpoint and a deployment; OpenAI wants a model name and
        nothing else, since its endpoint is fixed. Requiring an Azure resource
        for the semantic layer made it unreachable for anyone outside Aito,
        which is the wrong default for a repository anyone can clone."""
        if not self.embed_api_key:
            return False
        if self.embed_is_azure:
            return bool(self.embed_endpoint)   # deployment defaults
        return bool(self.embed_model)


    @staticmethod
    def from_env() -> "Config":
        # COMPANY_AI_ENV selects which dotenv file to load, so the same tools
        # can target different instances — e.g. COMPANY_AI_ENV=.env.aito to
        # point at Aito's own instance instead of the default demo .env. A
        # relative value resolves against the repo root. An explicitly chosen
        # file wins over the ambient environment (override=True); the default
        # .env keeps the prior "environment wins" behaviour.
        selected = os.environ.get("COMPANY_AI_ENV")
        env_path = Path(selected) if selected else Path(".env")
        if not env_path.is_absolute():
            env_path = REPO_ROOT / env_path
        load_dotenv(env_path, override=bool(selected))
        url = os.environ.get("AITO_INSTANCE_URL", "")
        assert url, (
            f"AITO_INSTANCE_URL is not set (loaded {env_path.name}). "
            "Copy .env.example to .env and fill it in."
        )
        data_dir = os.environ.get("COMPANY_AI_DATA_DIR", "")
        # the default source dir for `documents-import` (docs/25): a one-time
        # bulk import of an existing markdown knowledge dir into the Documents
        # store. Defaults to the repo's own docs; real deployments point it at
        # the private knowledge dir (strategy, memory, notes) to import once.
        library_dir = os.environ.get("COMPANY_AI_LIBRARY_DIR", "")
        # the dashboard port can live in the env file too, so an instance's
        # endpoint and port travel together (e.g. .env.aito). The CLI --port
        # flag still overrides it.
        port = os.environ.get("COMPANY_AI_PORT", "")
        config = Config(
            instance_url=url,
            api_key=os.environ.get("AITO_API_KEY", ""),
            data_dir=Path(data_dir) if data_dir else None,
            library_dir=Path(library_dir) if library_dir else REPO_ROOT / "docs",
            port=int(port) if port else 8770,
            # provider-agnostic; default to gpt-5-mini for testing. Swap to a
            # high-end model (or another provider) by changing env only.
            # Azure fields map from the operator's existing REACT_APP_OPENAI_*
            # vars; if an Azure endpoint is present and no provider is named,
            # default to azure (those creds only work the Azure way).
            llm_provider=_env_first(
                "COMPANY_AI_LLM_PROVIDER",
                default="azure" if _env_first("COMPANY_AI_LLM_AZURE_ENDPOINT",
                                              "REACT_APP_OPENAI_MODEL_URL") else "openai"),
            llm_model=_env_first("COMPANY_AI_LLM_MODEL", "REACT_APP_OPENAI_MODEL_NAME",
                                 default="gpt-5-mini"),
            llm_api_key=_env_first("COMPANY_AI_LLM_API_KEY", "REACT_APP_OPENAI_MODEL_API_KEY"),
            llm_base_url=_env_first("COMPANY_AI_LLM_BASE_URL"),
            llm_azure_endpoint=_env_first("COMPANY_AI_LLM_AZURE_ENDPOINT",
                                          "REACT_APP_OPENAI_MODEL_URL"),
            llm_azure_deployment=_env_first("COMPANY_AI_LLM_AZURE_DEPLOYMENT",
                                            "REACT_APP_OPENAI_MODEL_DEPLOYMENT"),
            llm_azure_api_version=_env_first("COMPANY_AI_LLM_AZURE_API_VERSION",
                                             "REACT_APP_OPENAI_MODEL_API_VERSION",
                                             default="2024-08-01-preview"),
            # web search is off unless a key is present; default the provider to
            # brave when a key is set (as the Azure default follows its creds).
            search_provider=_env_first(
                "COMPANY_AI_SEARCH_PROVIDER",
                default="brave" if _env_first("COMPANY_AI_SEARCH_API_KEY",
                                              "BRAVE_API_KEY", "BRAVE_SEARCH_API_KEY") else ""),
            search_api_key=_env_first("COMPANY_AI_SEARCH_API_KEY",
                                      "BRAVE_API_KEY", "BRAVE_SEARCH_API_KEY"),
            search_endpoint=_env_first("COMPANY_AI_SEARCH_ENDPOINT"),
            fetch_enabled=_env_first("COMPANY_AI_WEB_FETCH", default="on").lower()
            not in ("off", "0", "false", "no"),
            assistant_tools=[n.strip() for n in
                             _env_first("COMPANY_AI_ASSISTANT_TOOLS").split(",") if n.strip()],
            mcp_token=_env_first("COMPANY_AI_MCP_TOKEN"),
            operator_email=_env_first("COMPANY_AI_OPERATOR_EMAIL").strip().lower(),
            public_url=_env_first("COMPANY_AI_PUBLIC_URL").rstrip("/"),
            as_of=_parse_as_of(_env_first("COMPANY_AI_AS_OF")),
            # embeddings: its own endpoint/deployment; key falls back to the LLM
            # key (shared Azure resource). api-version defaults to the GA embeddings one.
            # Falls back to the CHAT resource's endpoint, the same way the key
            # already falls back to the chat key: when one Azure resource serves
            # both, naming it twice is just another thing to get wrong. An
            # embeddings resource in its own region still wins by being set.
            embed_endpoint=_env_first("COMPANY_AI_EMBED_ENDPOINT",
                                      "AZURE_OPENAI_ENDPOINT",
                                      "COMPANY_AI_LLM_AZURE_ENDPOINT",
                                      "REACT_APP_OPENAI_MODEL_URL").rstrip("/"),
            embed_deployment=_env_first("COMPANY_AI_EMBED_DEPLOYMENT",
                                        "AZURE_OPENAI_EMBED_DEPLOYMENT"),
            # the OpenAI path: a model name instead of an Azure deployment.
            # Explicit on purpose — the key already falls back to the LLM key,
            # so defaulting a model would switch embeddings (and billing) on
            # for anyone who merely has an LLM key set.
            embed_model=_env_first("COMPANY_AI_EMBED_MODEL"),
            embed_api_version=_env_first("COMPANY_AI_EMBED_API_VERSION", default="2024-02-01"),
            # OPENAI_API_KEY last: it is the name everyone already has set, so
            # accepting it saves a rename — but it is only ever a KEY. It never
            # switches embeddings on by itself; a model or deployment still has
            # to be named explicitly (see embed_enabled).
            public_demo=_env_first("COMPANY_AI_PUBLIC_DEMO").strip().lower() in ("1", "true", "yes"),
            embed_api_key=_env_first("COMPANY_AI_EMBED_API_KEY", "COMPANY_AI_LLM_API_KEY",
                                     "REACT_APP_OPENAI_MODEL_API_KEY", "OPENAI_API_KEY",
                                     "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_KEY"),
        )
        return _public_demo_posture(config)
