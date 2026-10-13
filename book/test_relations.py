"""The generic relate tool (td-20261013103434846142), on the seed.

Prints the Aito request, the strongest relations with their support, and what
was excluded as a restatement of the outcome, an identity, a time or free text.
"""

import json

import booktest as bt

from company_ai import loaders, relations
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key, 120)


def _show(t: bt.TestCaseRun, res: dict) -> None:
    t.tln(f"request: {json.dumps(res['request'], sort_keys=True)}")
    t.tln(f"population {res['population']}, with outcome {res['with_outcome']}")
    for r in res["relations"]:
        t.tln(f"  {r['field']}={r['value']!s:14} lift {r['lift']:.2f}  mi {r['mi']:.4f}  "
              f"rate {r['rate_with']} vs {r['rate_without']}  rows {r['rows_with']}"
              + ("  THIN" if r["thin"] else ""))
    t.tln(f"excluded: {', '.join(res['excluded'])}")


def test_relate_on_the_seed(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_touches(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)

    t.h1("What goes with reaching a person (touches)")
    res = relations.relate(client, "touches", {"reached": True}, top_n=8)
    _show(t, res)
    assert not {"outcome", "good_outcome", "booked", "contact_id"} & {
        r["field"] for r in res["relations"]}, "a restatement or an identity was reported"

    t.h1("Within calls only")
    _show(t, relations.relate(client, "touches", {"reached": True}, where={"channel": "call"},
                              top_n=6))

    t.h1("What goes with losing a deal (deals)")
    _show(t, relations.relate(client, "deals", {"won": False}, top_n=6))

    t.h1("A field the table does not have is refused")
    try:
        relations.relate(client, "touches", {"no_such_field": True})
    except AssertionError as e:
        t.tln(f"refused: {e}")
