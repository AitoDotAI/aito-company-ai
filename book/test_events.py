"""Events-to-attend gate: the go/no-go lifecycle (candidate → go / no_go →
attended, with an outcome). Requires a running Aito instance.
"""

import booktest as bt

from company_ai import loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def test_events_seed(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    n = loaders.load_events(client, SEED_DIR)
    rows = client.query({"from": "events", "limit": 1000})["hits"]
    from collections import Counter
    t.h1("Events seed: the status mix")
    t.tln(f"loaded {n}")
    t.tln(f"status mix: {dict(sorted(Counter(e['status'] for e in rows).items()))}")


def test_go_no_go_lifecycle(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.clear_table(client, "events")

    t.h1("record a candidate → go → attended(worthwhile)")
    ev = log.add_event(client, name="ProductCon 2026", type="conference",
                       starts="2026-07-15", location="Berlin", cost_eur=600)
    t.tln(f"candidate: status={ev['status']} decided={ev['decided']} outcome={ev['outcome']}")
    g = log.decide_event(client, ev["event_id"], "go", notes="worth a talk")
    t.tln(f"go: status={g['status']} decided_set={bool(g['decided'])}")
    a = log.decide_event(client, ev["event_id"], "attended", outcome="worthwhile")
    t.tln(f"attended: status={a['status']} outcome={a['outcome']}")
    assert a["status"] == "attended" and a["outcome"] == "worthwhile"

    t.h1("an outcome on a non-attended event is refused (rule 3)")
    try:
        log.decide_event(client, ev["event_id"], "go", outcome="worthwhile")
        raise RuntimeError("accepted outcome on a non-attended event")
    except AssertionError as e:
        t.tln(str(e))

    t.h1("unknown event id raises")
    try:
        log.decide_event(client, "nope", "go")
        raise RuntimeError("decided an unknown event")
    except AssertionError as e:
        t.tln(str(e))
