"""`_modify` read-visibility (docs/24 bug 5) — re-probed per engine build.

An update was applied but stayed INVISIBLE to reads until the next write to the
collection: not a lost write, a read-visibility bug. It is why
`AitoClient.update_entries` carries a built-in `optimize` — the only correct
`_modify` update is a flushed one — and why a caller that forgets is left with
a table that reads stale with no error.

This probe writes to a scratch table of its own and drops it again, so it can
be re-run on any build to answer one question: does it still reproduce?
"""

import time

import booktest as bt

from company_ai.aito import AitoClient
from company_ai.config import Config

TABLE = "_modify_visibility_probe"
SCHEMA = {"type": "table",
          "columns": {"id": {"type": "String"}, "val": {"type": "String"}}}


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _val(client: AitoClient, row_id: str) -> str | None:
    hits = client.query({"from": TABLE, "where": {"id": row_id},
                         "select": ["val"], "limit": 1}).get("hits", [])
    return hits[0]["val"] if hits else None


def test_modify_update_is_visible_to_the_next_read(t: bt.TestCaseRun) -> None:
    client = _client()
    t.h1(f"engine build: {client.version().get('version')}")

    client.delete_table(TABLE)
    client.create_table(TABLE, SCHEMA)
    client.upload_batch(TABLE, [{"id": "r1", "val": "before"},
                                {"id": "r2", "val": "before"}])
    t.tln(f"  seeded: r1={_val(client, 'r1')} r2={_val(client, 'r2')}")

    # The RAW modify, deliberately without the optimize that update_entries
    # adds — the whole point is what a caller sees when nothing flushes.
    client._request("POST", "/api/v2/data/_modify",
                    {"update": TABLE, "where": {"id": "r2"}, "set": {"val": "AFTER"}})

    t.h1("read back immediately, with no intervening write")
    seen = [_val(client, "r2")]
    for _ in range(4):                      # a few seconds, as docs/24 did
        time.sleep(1)
        seen.append(_val(client, "r2"))
    t.tln(f"  r2 over ~4s: {seen}")
    visible_unflushed = seen[-1] == "AFTER"
    t.tln(f"  visible without a flush: {visible_unflushed}")

    t.h1("after an optimize (the flush update_entries performs)")
    client.optimize(TABLE)
    after_flush = _val(client, "r2")
    t.tln(f"  r2 = {after_flush}")
    t.tln(f"  r1 untouched = {_val(client, 'r1')}")

    t.h1("verdict")
    t.tln("  docs/24 bug 5 REPRODUCES — an unflushed update reads stale"
          if not visible_unflushed else
          "  docs/24 bug 5 does NOT reproduce on this build — the update is"
          " visible to the next read without a flush")

    # The write must land either way: invisible-until-flushed is the bug being
    # measured, a LOST update would be a different and far worse one. Assert
    # BEFORE dropping the table — reading a dropped table is a 404, not a
    # finding.
    assert after_flush == "AFTER", "the update did not land even after a flush"
    assert _val(client, "r1") == "before", "the update touched the wrong row"
    client.delete_table(TABLE)
