"""Query gate (docs/04-testing.md gate 2): the three brief queries on
both datasets, request/response/derived printed for review.

as_of is pinned to the seed generator's AS_OF so snapshots never depend
on the run date. Requires a running Aito instance.
"""

import json
from datetime import date

import booktest as bt

from company_ai import loaders, queries
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, SEED_TINY_DIR, Config

AS_OF = date(2026, 6, 12)  # friday; matches scripts/generate_seed.py


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _load(client: AitoClient, data_dir) -> None:
    loaders.create_schema(client)
    loaders.load_rolodex(client, data_dir)
    loaders.load_touches(client, data_dir)


def _print_result(t: bt.TestCaseRun, result: queries.Result) -> None:
    t.h2("Aito calls")
    for request, response in result.calls:
        t.tln(f"request:  {json.dumps(request, sort_keys=True)}")
        if "predict" in request or "orderBy" in request:
            t.tln(f"response: {json.dumps(response, sort_keys=True)}")
        else:
            t.tln(f"response: total={response['total']} (rows omitted)")
    t.h2("Derived")
    t.tln(json.dumps(result.derived, indent=2, sort_keys=True))


def _all_queries(t: bt.TestCaseRun, data_dir, opener_contact: str) -> None:
    client = _client()
    _load(client, data_dir)

    t.h1("Query 3: what changed")
    _print_result(t, queries.what_changed(client, as_of=AS_OF))

    t.h1("Query 1: who to call, window 0800")
    _print_result(t, queries.who_to_call(client, "0800", top_n=5, as_of=AS_OF))

    t.h1(f"Query 2: opener context for {opener_contact}")
    _print_result(t, queries.opener_context(client, opener_contact))


def test_brief_queries_seed(t: bt.TestCaseRun) -> None:
    _all_queries(t, SEED_DIR, "sc001")


def test_brief_queries_seed_tiny(t: bt.TestCaseRun) -> None:
    _all_queries(t, SEED_TINY_DIR, "yc002")
