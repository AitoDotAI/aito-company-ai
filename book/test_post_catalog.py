"""The marketing catalog read surface, and engagement on a post result.

Before a backfill, an agent has to see what is already there: which materials,
channels and posts exist, so a post logged twice or a material added again is
caught first. Until 4.11.2026 materials, channels and posts could only be
written, over MCP and over the API alike. These reads list them with filters;
`title` finds a material by words of its title (Aito text match).

A post's result also carries its engagement (reactions, comments, reposts,
link clicks), nullable and recorded as given. None of them feeds the scorer,
whose features are a fixed list (scorer.FEATURES).
"""

import json

import booktest as bt
from fastapi.testclient import TestClient

from company_ai import catalog, loaders, log, relations
from company_ai.aito import AitoClient
from company_ai.api import create_app
from company_ai.config import SEED_DIR, Config
from company_ai.server import mcp


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key, 120)


def _seeded() -> AitoClient:
    client = _client()
    loaders.create_schema(client)
    for load in (loaders.load_materials, loaders.load_channels, loaders.load_posts):
        load(client, SEED_DIR)
    return client


def test_catalog_reads(t: bt.TestCaseRun) -> None:
    client = _seeded()

    t.h1("Channels on LinkedIn")
    channels = catalog.list_channels(client, platform="linkedin")
    for c in channels:
        t.tln(f"{c['channel_id']} {c['name']} ({c['platform']})")
    assert channels and all(c["platform"] == "linkedin" for c in channels)

    t.h1("Materials whose title mentions a word")
    every = catalog.list_materials(client)
    word = every[0]["title"].split()[0]
    t.tln(f"{len(every)} materials; finding {word!r}")
    found = catalog.list_materials(client, title=word)
    for m in found:
        t.tln(f"{m['material_id']} {m['title']!r} topic={m['topic']} lane={m['lane']}")
    assert found and len(found) < len(every), f"title match {word!r} did not narrow"

    t.h1("Posts of one material, newest first")
    material_id = every[0]["material_id"]
    posts = catalog.list_posts(client, material_id=material_id)
    for p in posts:
        t.tln(f"{p['post_id']} {p['status']} {p.get('posted_at')} {p['platform']} "
              f"reach={p.get('reach_or_views')} outcome={p.get('outcome')}")
    assert all(p["material_id"] == material_id for p in posts)
    dates = [p.get("posted_at") for p in posts if p.get("posted_at")]
    assert dates == sorted(dates, reverse=True), f"not newest first: {dates}"

    t.h1("Posted posts on LinkedIn")
    linkedin = catalog.list_posts(client, platform="linkedin", status="posted")
    t.tln(f"{len(linkedin)} posts")
    assert linkedin and all(p["platform"] == "linkedin" and p["status"] == "posted"
                            for p in linkedin)

    t.h1("An unknown filter value raises")
    for call in (lambda: catalog.list_channels(client, platform="myspace"),
                 lambda: catalog.list_posts(client, status="maybe")):
        try:
            call()
            raise RuntimeError("accepted an unknown value")
        except AssertionError as e:
            t.tln(str(e))


async def test_catalog_reads_over_mcp_and_api(t: bt.TestCaseRun) -> None:
    client = _seeded()
    t.h1("MCP tools")
    tools = {x.name: x for x in await mcp.list_tools()}
    for name in ("list_materials", "list_channels", "list_posts"):
        assert name in tools, f"no MCP tool {name}"
        t.tln(f"{name}: {sorted(tools[name].inputSchema.get('properties', {}))}")

    t.h1("API reads agree with the module")
    api = TestClient(create_app())
    for path, direct in (
            ("/api/materials", catalog.list_materials(client)),
            ("/api/channels?platform=linkedin", catalog.list_channels(client, platform="linkedin")),
            ("/api/posts?status=posted", catalog.list_posts(client, status="posted"))):
        response = api.get(path)
        assert response.status_code == 200, f"GET {path} -> {response.status_code}: {response.text[:200]}"
        rows = next(iter(response.json().values()))
        t.tln(f"GET {path} -> {len(rows)} rows")
        assert rows == direct, f"GET {path} differs from the module"


def test_post_result_records_engagement(t: bt.TestCaseRun) -> None:
    client = _seeded()
    post = catalog.list_posts(client, status="planned")[0]
    t.h1("Log a result with engagement")
    row = log.log_post_result(client, post["post_id"], outcome="modest", reach_or_views=900,
                              posted_at="2026-10-14", reactions=31, comments=4,
                              reposts=2, link_clicks=17)
    t.tln(json.dumps({k: row.get(k) for k in ("post_id", "posted_at", "weekday", "reach_or_views",
                                          "reactions", "comments", "reposts", "link_clicks")},
                     sort_keys=True))
    assert (row["reactions"], row["comments"], row["reposts"], row["link_clicks"]) == (31, 4, 2, 17)

    t.h1("Without engagement the columns stay null, not zero")
    other = catalog.list_posts(client, status="planned")[0]
    bare = log.log_post_result(client, other["post_id"], outcome="flop", reach_or_views=40,
                               posted_at="2026-10-15")
    t.tln(json.dumps({k: bare.get(k) for k in ("reactions", "comments", "reposts", "link_clicks")},
                     sort_keys=True))
    assert all(bare.get(k) is None for k in ("reactions", "comments", "reposts", "link_clicks"))

    t.h1("A negative count raises")
    try:
        log.log_post_result(client, other["post_id"], outcome="flop", reach_or_views=40,
                            posted_at="2026-10-15", reactions=-1)
        raise RuntimeError("accepted a negative count")
    except AssertionError as e:
        t.tln(str(e))

    t.h1("Engagement restates the outcome, so relate excludes it")
    t.tln(f"posts leaks: {sorted(relations.LEAKS['posts'])}")
    assert {"reactions", "comments", "reposts", "link_clicks"} <= relations.LEAKS["posts"]
