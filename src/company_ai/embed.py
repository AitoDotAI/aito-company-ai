"""Embeddings for semantic / cross-lingual smart search (docs/23).

Azure OpenAI `text-embedding-3-large`, addressed by deployment (its own endpoint,
often a different region than the chat model). Embeddings are a **load-time
featurization**: Python turns text into a vector, and Aito owns the ranking
(`$vectorSimilarity` / `$nearest`). No score, ranking, or prediction is computed
here — rule 2 is intact; this is the same seam as `llm.py` (a swappable provider
behind `Config`).

Off unless configured (`Config.embed_enabled`): `embedder()` returns `None`, and
every caller falls back to pure text-`$match`. No silent failure otherwise — a
non-200 raises (rule 3).
"""

import requests

from .config import Config
from .schema import EMBED_DIM   # 1000 — capped to this Aito build's Vector limit

_BATCH = 96               # inputs per request (well under Azure's per-call limits)


class EmbedError(RuntimeError):
    pass


def embedder(config: Config):
    """Return `embed(texts) -> list[list[float]]`, or `None` when embeddings are
    not configured (search then stays pure text-match). The returned callable
    batches its inputs and preserves input order; a non-200 raises loudly."""
    if not config.embed_enabled:
        return None

    url = (f"{config.embed_endpoint}/openai/deployments/{config.embed_deployment}"
           f"/embeddings?api-version={config.embed_api_version}")
    headers = {"api-key": config.embed_api_key, "content-type": "application/json"}

    def embed(texts: list[str]) -> list[list[float]]:
        items = [t if t and t.strip() else " " for t in texts]  # Azure rejects empty input
        out: list[list[float]] = []
        for i in range(0, len(items), _BATCH):
            chunk = items[i:i + _BATCH]
            # `dimensions` asks text-embedding-3-large for a shorter vector
            # (Matryoshka) so it fits this Aito build's Vector-column cap (1017).
            r = requests.post(url, headers=headers,
                              json={"input": chunk, "dimensions": EMBED_DIM}, timeout=60)
            if r.status_code != 200:
                raise EmbedError(f"embeddings -> {r.status_code}: {r.text[:300]}")
            data = sorted(r.json()["data"], key=lambda d: d["index"])
            out.extend(d["embedding"] for d in data)
        return out

    return embed
