"""Where a request's time goes (td-20261014122004215297).

One log line per dashboard request and per MCP tool call: the total time, how
many Aito round trips it made, how long they took, and how many bytes came
back. "It feels slow" then has an answer per call: many round trips (N+1, a
read-back and a flush after every write), a few slow ones (engine time), big
responses (whole-table reads), or little Aito time at all (our own code).

Lines go to stderr: on the stdio MCP server stdout IS the protocol.
"""

import functools
import sys
import time
from contextlib import contextmanager

from .aito import TRACE

SLOW_MS = 0          # log every call; raise to log only the slow ones


def summarize(trace: list[dict], total_ms: float) -> dict:
    aito_ms = sum(c["ms"] for c in trace)
    return {
        "total_ms": round(total_ms, 1),
        "aito_calls": len(trace),
        "aito_ms": round(aito_ms, 1),
        "other_ms": round(total_ms - aito_ms, 1),
        "received_kb": round(sum(c["received"] for c in trace) / 1024, 1),
        "slowest": max(trace, key=lambda c: c["ms"]) if trace else None,
    }


@contextmanager
def measure(label: str, log: bool = True):
    """Collect the Aito calls made inside the block; log a one-line summary.
    Yields the summary dict, filled in when the block exits."""
    trace: list[dict] = []
    token = TRACE.set(trace)
    started = time.perf_counter()
    out: dict = {}
    try:
        yield out
    finally:
        TRACE.reset(token)
        out.update(summarize(trace, (time.perf_counter() - started) * 1000))
        if log and out["total_ms"] >= SLOW_MS:
            slow = out["slowest"]
            print(f"[timing] {label} {out['total_ms']:.0f}ms "
                  f"aito={out['aito_calls']}x/{out['aito_ms']:.0f}ms "
                  f"other={out['other_ms']:.0f}ms recv={out['received_kb']}KB"
                  + (f" slowest={slow['method']} {slow['path']} {slow['ms']:.0f}ms" if slow else ""),
                  file=sys.stderr, flush=True)


def wrap_mcp_tools(mcp) -> int:
    """Time every registered MCP tool. The tool keeps its validated signature
    (FastMCP built it at registration); only the function it calls is wrapped."""
    tools = mcp._tool_manager._tools
    assert tools, "no MCP tools registered yet"
    for name, tool in tools.items():
        assert not tool.is_async, f"{name}: async tools are not wrapped"
        fn = tool.fn

        @functools.wraps(fn)
        def timed(*args, __fn=fn, __name=name, **kwargs):
            with measure(f"mcp:{__name}"):
                return __fn(*args, **kwargs)
        tool.fn = timed
    return len(tools)
