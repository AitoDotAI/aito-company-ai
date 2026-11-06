"""A kind-filtered semantic search fills its page (td-20261106231240519861).
`$nearest` ran over the whole vector index and the kind was filtered after,
so on the seed a doc search for 10 came back with 0 docs: deals, contacts and
facts filled the over-fetch. Requires a running Aito instance and embeddings."""

import booktest as bt

from company_ai import embed, loaders, search
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

FR = "quels prospects contacter au sujet des prix"


def test_a_doc_search_returns_docs_not_an_empty_page(t: bt.TestCaseRun) -> None:
    cfg = Config.from_env()
    if not cfg.embed_enabled:
        t.tln("SKIPPED: needs an embeddings deployment")
        return
    client, embedder = AitoClient(cfg.instance_url, cfg.api_key), embed.embedder(cfg)
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    loaders.load_documents(client, SEED_DIR)
    stats = search.build_index(client, embed=embedder)
    docs = stats["by_kind"]["doc"]
    t.h1(f"index: {stats['by_kind']}")
    for kind, n in (("doc", 10), ("doc", 3), ("contact", 10)):
        hits = search._vector_candidates(client, embedder, FR, kind, n)
        want = min(n, stats["by_kind"][kind])
        t.tln(f"  kind={kind} n={n}: {len(hits)} hits (want {want}), all {kind}: "
              f"{all(h['kind'] == kind for h in hits)}")
        assert len(hits) == want and all(h["kind"] == kind for h in hits), (kind, n, len(hits))
    sims = [h["$similarity"] for h in search._vector_candidates(client, embedder, FR, "doc", docs)]
    t.tln(f"  every doc reachable, most similar first: {len(sims) == docs and sims == sorted(sims, reverse=True)}")
    assert len(sims) == docs and sims == sorted(sims, reverse=True)
