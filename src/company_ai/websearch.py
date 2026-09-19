"""Web search for the assistant, abstracted behind a provider.

This is the assistant's one *non-Aito* tool (CLAUDE.md rule 1b, docs/16). It
is still a read: the model issues a query and narrates the ranked results —
it does not reason, score, or predict, and rule 2 still owns every internal
number (those come only from the Aito-backed tools). Web search adds *external*
facts Aito cannot hold: company news, market moves, a person's current role.

Held to the same invariants as `llm.py`:

  - The provider is swappable by env alone (`Config.search_*`); Brave today,
    another backend later with no change to the assistant.
  - No silent failure (rule 3): a provider named without a key raises loudly;
    a non-200 from the backend raises. The assistant surfaces the error to the
    model as the tool result rather than hiding it.
  - Off by default: with no key configured, `make_search_client` returns None
    and the assistant simply does not advertise the tool.

Privacy (docs/06): the query text leaves the machine and reaches the search
provider. The operator's typed questions are what get sent; keep real,
non-public specifics out of them the same way you would out of any web search.
"""

import re
from dataclasses import dataclass
from typing import Protocol

import requests

from .config import Config

_TAGS = re.compile(r"<[^>]+>")  # Brave marks up snippets with <strong>…</strong>


class SearchError(RuntimeError):
    pass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    age: str = ""   # provider's freshness hint, e.g. "2 days ago" (may be "")


class WebSearchClient(Protocol):
    provider: str

    def search(self, query: str, count: int = 5) -> list[SearchResult]:
        ...


def _clean(text: str) -> str:
    return _TAGS.sub("", text or "").strip()


@dataclass
class BraveSearch:
    """Brave Search API. Independent index, api-key via the
    `X-Subscription-Token` header. Endpoint returns `web.results[]` with
    `title`, `url`, `description` (the snippet), and an optional `age`."""

    api_key: str
    endpoint: str = "https://api.search.brave.com/res/v1/web/search"
    provider: str = "brave"

    def search(self, query: str, count: int = 5) -> list[SearchResult]:
        if not self.api_key:
            raise SearchError("no web-search key: set COMPANY_AI_SEARCH_API_KEY "
                              "(or BRAVE_API_KEY) in the env file")
        count = max(1, min(int(count), 10))  # keep the model's context tight
        response = requests.get(
            self.endpoint,
            headers={"X-Subscription-Token": self.api_key,
                     "Accept": "application/json"},
            params={"q": query, "count": count},
            timeout=15)
        if response.status_code != 200:
            raise SearchError(
                f"Brave search -> {response.status_code}: {response.text[:200]}")
        results = (response.json().get("web") or {}).get("results") or []
        return [SearchResult(title=_clean(r.get("title", "")),
                             url=r.get("url", ""),
                             snippet=_clean(r.get("description", "")),
                             age=r.get("age", "") or "")
                for r in results[:count]]


def make_search_client(config: Config) -> WebSearchClient | None:
    """Build the assistant's search provider from config, or None when search
    is not configured (the feature is simply off). A provider named *with a
    missing key* raises — a half-configured backend must not fail silently."""
    provider = (config.search_provider or "").lower()
    if not provider:
        return None
    if provider == "brave":
        if not config.search_api_key:
            raise SearchError(
                "COMPANY_AI_SEARCH_PROVIDER=brave but no key; set "
                "COMPANY_AI_SEARCH_API_KEY (or BRAVE_API_KEY)")
        return BraveSearch(api_key=config.search_api_key,
                           endpoint=config.search_endpoint
                           or BraveSearch.endpoint)
    raise SearchError(
        f"unknown search provider {config.search_provider!r}; supported: brave")
