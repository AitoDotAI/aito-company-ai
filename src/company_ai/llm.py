"""The app's LLM, abstracted behind a provider.

A language model runs inside the app in exactly two places — the board
composer (`board.py`) and the dashboard assistant (`assistant.py`) — both
held to the repo's invariants:

  - Rule 2 stays intact: the LLM never scores, ranks, predicts, or weights.
    Every number it surfaces is one Aito already produced. The composer turns
    Aito outputs into prose; the assistant chooses which Aito-backed tool to
    call and narrates the result. Neither computes inference.
  - The provider is swappable by env alone (Config.llm_*), so gpt-5-mini for
    testing becomes a high-end model later with no code change. The seam for
    an Anthropic/Claude provider is marked below.
  - No silent failure (rule 3): a missing key or a non-200 raises loudly.

Two surfaces on each client: `complete(system, user)` (one-shot prose, the
composer) and `chat(messages, tools)` (returns the raw assistant message,
which may carry tool_calls — the assistant's agent loop drives the rounds).
"""

from dataclasses import dataclass
from typing import Protocol

import requests

from .config import Config


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    model: str

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        ...

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             max_tokens: int = 1024) -> dict:
        ...


def _messages(system: str, user: str) -> list[dict]:
    return [{"role": "system", "content": system},
            {"role": "user", "content": user}]


def _message(response: requests.Response, label: str) -> dict:
    """The assistant message dict (role/content/tool_calls), or raise loudly."""
    if response.status_code != 200:
        raise LLMError(f"LLM {label} -> {response.status_code}: {response.text[:300]}")
    return response.json()["choices"][0]["message"]


def _body(messages: list[dict], tools: list[dict] | None, max_tokens: int,
          model: str | None) -> dict:
    body = {"messages": messages, "max_completion_tokens": max_tokens}
    if model:
        body["model"] = model
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    return body


@dataclass
class OpenAICompatClient:
    """Vanilla OpenAI (or any Bearer-auth, /chat/completions-compatible
    gateway). The default base_url is OpenAI's API. NOT for Azure — Azure uses
    a deployment URL and an api-key header; see AzureOpenAIClient."""

    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"

    def _url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _send(self, body: dict) -> dict:
        if not self.api_key:
            raise LLMError("no LLM api key: set COMPANY_AI_LLM_API_KEY in the env file "
                           "(the LLM surfaces need it; Aito access is separate)")
        response = requests.post(self._url(),
                                 headers={"Authorization": f"Bearer {self.api_key}"},
                                 json=body, timeout=120)
        return _message(response, self.model)

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return self._send(_body(_messages(system, user), None, max_tokens, self.model))["content"]

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             max_tokens: int = 1024) -> dict:
        return self._send(_body(messages, tools, max_tokens, self.model))


@dataclass
class AzureOpenAIClient:
    """Azure OpenAI. Differs from vanilla OpenAI in three ways: the model is
    addressed by *deployment* in the URL, auth is an `api-key` header (not a
    Bearer token), and the api-version is a required query param. Endpoint is
    the resource/region URL, e.g.
    https://<region>.api.cognitive.microsoft.com or
    https://<resource>.openai.azure.com."""

    api_key: str
    endpoint: str
    deployment: str
    api_version: str
    model: str = ""   # label only (the deployment selects the model)

    @property
    def url(self) -> str:
        return (f"{self.endpoint.rstrip('/')}/openai/deployments/{self.deployment}"
                f"/chat/completions?api-version={self.api_version}")

    def _send(self, body: dict) -> dict:
        if not self.api_key:
            raise LLMError("no Azure OpenAI key: set COMPANY_AI_LLM_API_KEY (or "
                           "REACT_APP_OPENAI_MODEL_API_KEY) in the env file")
        if not (self.endpoint and self.deployment):
            raise LLMError("Azure OpenAI needs an endpoint and a deployment "
                           "(REACT_APP_OPENAI_MODEL_URL / _DEPLOYMENT)")
        response = requests.post(self.url, headers={"api-key": self.api_key},
                                 json=body, timeout=120)
        return _message(response, self.deployment or self.model)

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        # Azure selects the model by deployment, so no model in the body.
        return self._send(_body(_messages(system, user), None, max_tokens, None))["content"]

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             max_tokens: int = 1024) -> dict:
        return self._send(_body(messages, tools, max_tokens, None))


# Seam for the high-end swap: an Anthropic provider with the same
# .complete(system, user) signature. Add it here and set
# COMPANY_AI_LLM_PROVIDER=anthropic; nothing else changes.


def make_client(config: Config) -> LLMClient:
    """Build the composer's LLM from config. Unknown provider raises."""
    provider = config.llm_provider.lower()
    if provider in ("azure", "azure-openai"):
        return AzureOpenAIClient(
            api_key=config.llm_api_key,
            endpoint=config.llm_azure_endpoint,
            deployment=config.llm_azure_deployment,
            api_version=config.llm_azure_api_version,
            model=config.llm_model,
        )
    if provider in ("openai", "openai-compat", "gpt"):
        return OpenAICompatClient(
            api_key=config.llm_api_key,
            model=config.llm_model,
            base_url=config.llm_base_url or "https://api.openai.com/v1",
        )
    raise LLMError(
        f"unknown LLM provider {config.llm_provider!r}; supported: azure, openai "
        "(add an Anthropic provider in llm.py to swap to a high-end model)")
