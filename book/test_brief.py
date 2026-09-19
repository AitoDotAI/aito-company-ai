"""Phase C gate: the no-llm brief on both datasets, snapshot-reviewed.

The rendering must fit one phone screen (~40 lines is the budget used
here; the acceptance bar in docs/05-phases.md). as_of pinned to the
generator's AS_OF.
"""

from datetime import date

import booktest as bt

from company_ai import brief, loaders
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, SEED_TINY_DIR, Config

AS_OF = date(2026, 6, 12)
PHONE_SCREEN_LINES = 40


def _render(data_dir, window: str) -> str:
    config = Config.from_env()
    client = AitoClient(config.instance_url, config.api_key)
    loaders.create_schema(client)
    loaders.load_rolodex(client, data_dir)
    loaders.load_touches(client, data_dir)
    loaders.load_todos(client, data_dir)   # the DO NEXT block reads todos
    return brief.render_brief(client, window, AS_OF)


def test_brief_seed(t: bt.TestCaseRun) -> None:
    t.h1("brief --no-llm, seed, window 0800")
    text = _render(SEED_DIR, "0800")
    t.tln(text)
    lines = text.count("\n") + 1
    assert lines <= PHONE_SCREEN_LINES, f"brief is {lines} lines, over the phone screen"
    t.tln("")
    t.tln(f"({lines} lines <= {PHONE_SCREEN_LINES})")


def test_brief_seed_tiny(t: bt.TestCaseRun) -> None:
    t.h1("brief --no-llm, seed_tiny, window 1600")
    text = _render(SEED_TINY_DIR, "1600")
    t.tln(text)
    lines = text.count("\n") + 1
    assert lines <= PHONE_SCREEN_LINES, f"brief is {lines} lines, over the phone screen"
    t.tln("")
    t.tln(f"({lines} lines <= {PHONE_SCREEN_LINES})")
