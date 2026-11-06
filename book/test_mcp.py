"""Phase B gate: the MCP tool surface.

The three query tools' requests and responses are snapshotted in
test_queries.py; here the snapshot covers the tool registry itself
(names, signatures), the decision log write, and the predict escape
hatch — everything Claude can reach over MCP.
"""

import json
from datetime import datetime

import booktest as bt

from company_ai import loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config
from company_ai.server import mcp


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


async def test_tool_registry(t: bt.TestCaseRun) -> None:
    t.h1("Registered MCP tools")
    for tool in await mcp.list_tools():
        t.h2(tool.name)
        t.tln(f"params: {sorted(tool.inputSchema.get('properties', {}))}")
        t.tln(f"required: {sorted(tool.inputSchema.get('required', []))}")
        t.tln(tool.description or "")


async def test_log_post_result_takes_posted_at(t: bt.TestCaseRun) -> None:
    t.h1("log_post_result accepts the date the post went out")
    t.tln("A backfilled post logged without it is stamped today, and its weekday")
    t.tln("(a scorer feature) with it.")
    tool = next(x for x in await mcp.list_tools() if x.name == "log_post_result")
    params = sorted(tool.inputSchema.get("properties", {}))
    t.tln(f"params: {params}")
    assert "posted_at" in params, f"log_post_result drops posted_at: {params}"


def test_log_decision(t: bt.TestCaseRun) -> None:
    t.h1("log_decision writes a decisions row")
    client = _client()
    loaders.create_schema(client)
    client.delete_table("decisions")
    loaders.create_schema(client)

    row = log.log_decision(
        client,
        decision_type="call_priority",
        context={"window": "0800", "weekday": "fri", "segment": "accounting",
                 "tier": "A", "ai_lifecycle": "operating"},
        chosen="sc032",
        agent_confidence=0.33,
        human_action="overridden",
        human_alternative="sc018",
        ts=datetime(2026, 6, 12, 8, 5),
    )
    t.tln(json.dumps(row, sort_keys=True))
    stored = client.query({"from": "decisions", "limit": 10})
    t.tln(f"rows in decisions: {stored['total']}")
    t.tln(json.dumps(stored["hits"], indent=2, sort_keys=True))


def test_predict_escape_hatch(t: bt.TestCaseRun) -> None:
    """The escape hatch passes a predict through to Aito unchanged. Its $p
    are Aito's and are pinned exactly, but they move with the engine: both
    re-accepts of this snapshot were engine bumps with the data unchanged
    (2.11.2; 2.11.4 -> 2.11.6), td-20260926215926901519. So the engine build
    is printed beside them, and a diff that moves the numbers shows whether
    the engine moved too. What the hatch itself promises is asserted."""
    t.h1("predict: ad-hoc question through the escape hatch")
    client = _client()
    build = client.version()
    t.tln(f"engine build: {build.get('version')} ({build.get('gitRevision', '')[:8]})")
    loaders.create_schema(client)
    loaders.load_rolodex(client, SEED_DIR)
    loaders.load_touches(client, SEED_DIR)

    request = {
        "from": "touches",
        "where": {"contact_id.segment": "accounting", "channel": "call"},
        "predict": "window",
        "limit": 4,
    }
    t.tln(f"request:  {json.dumps(request, sort_keys=True)}")
    response = client.predict(request)
    t.tln(f"response: {json.dumps(response, sort_keys=True)}")
    from company_ai import schema
    hits = response["hits"]
    assert [h["$value"] for h in hits if h["$value"] not in schema.WINDOWS] == [], hits
    assert len(hits) == len(schema.WINDOWS), "every window is a candidate"
    assert [h["$p"] for h in hits] == sorted((h["$p"] for h in hits), reverse=True), "Aito's order"
    assert abs(sum(h["$p"] for h in hits) - 1) < 1e-6, "a distribution over the windows"
