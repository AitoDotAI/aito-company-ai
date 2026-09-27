"""Semantic / cross-lingual smart search (docs/23) — the vector capability that
closes the `test_agent_gaps` cross-lingual gap.

GATED: needs an Azure embeddings deployment (Config.embed_enabled) AND network,
so it is skipped in the default offline harness and run intentionally with
`COMPANY_AI_EMBED_*` set (against a test Aito). When it runs it proves the flip:
a French query that finds nothing by text-`$match` returns the right documents
once `ranked()` blends `$nearest` over `search_vectors`. All ranking stays Aito's
(rule 2); embeddings only featurize.
"""

import booktest as bt

from company_ai import embed, loaders, search
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _ready(t: bt.TestCaseRun):
    """The embedder, or None (skip) when embeddings aren't configured."""
    cfg = Config.from_env()
    if not cfg.embed_enabled:
        t.tln("SKIPPED — semantic search needs an Azure embeddings deployment.")
        t.tln("Set COMPANY_AI_EMBED_ENDPOINT / _DEPLOYMENT / _API_KEY and run against")
        t.tln("a test Aito to exercise it (it embeds the seed corpus via the API).")
        return None, None
    client = AitoClient(cfg.instance_url, cfg.api_key)
    return client, embed.embedder(cfg)


def test_crosslingual_query_flips_from_empty_to_semantic(t: bt.TestCaseRun) -> None:
    client, embedder = _ready(t)
    if embedder is None:
        return

    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)
    stats = search.build_index(client, embed=embedder)
    t.h1("index built, with embeddings")
    t.tln(f"indexed {stats['indexed']} items; vectors {stats.get('vectors')}")

    fr = "quels prospects contacter au sujet des prix"   # 'which prospects to contact about pricing'
    t.h1(f"a French query over English documents: '{fr}'")

    # Print the REQUESTS as well as the hits. This snapshot is the artifact the
    # capability is shown with, and "a French query returns English documents"
    # is only convincing next to the query that did it.
    text_res = search.search(client, fr, kind="doc")
    for label, request, response in text_res.calls:
        t.tln(f"  {label} request:  {request}")
        t.tln(f"  {label} returned: {len(response.get('hits', []))} hits")
    text_hits = [h["title"] for h in text_res.derived["hits"]]

    blend_res = search.ranked(client, fr, kind="doc", embed=embedder)
    blended = blend_res.derived
    for label, request, response in blend_res.calls:
        t.tln(f"  {label} request:  {request}")
    sem_hits = [h["title"] for h in blended["hits"]]
    t.tln("")
    t.tln(f"text-match ($match):   {len(text_hits)} hits  {text_hits}")
    # The exact hit COUNT is deliberately not snapshotted. An embedding service
    # is not bit-deterministic, so the tail of a $nearest result set moves
    # between runs — two runs here returned 6 and 7 hits, identical for the
    # first six. Pinning the whole list would make this test flap for a reason
    # that says nothing about the capability; the flip and the leading hits are
    # the claim, so those are what the snapshot holds.
    t.tln(f"blended (+ $nearest):  semantic={blended['semantic']}, top 5:")
    for h in blended["hits"][:5]:
        t.tln(f"   [{h['kind']}] {h['title']}")

    # the flip: text-match finds nothing (no shared tokens); the vector blend does
    assert text_hits == [], "text-match should still find nothing for the French query"
    assert blended["semantic"] and len(sem_hits) > 0, "the vector blend must return semantic hits"
    assert all(h["kind"] == "doc" for h in blended["hits"]), "kind filter honoured"

    t.h1("an English exact query keeps its exact match (interleave, not vector-only)")
    en = search.ranked(client, "pricing", kind="doc", embed=embedder).derived
    t.tln(f"'pricing' -> {[h['title'] for h in en['hits']]}")
    assert en["count"] > 0
