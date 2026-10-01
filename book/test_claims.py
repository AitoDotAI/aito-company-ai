"""No surface claims Aito's probabilities are calibrated (td-20260930191344950920 item 5).

"Calibrated" is a measured property: of the deals read at 30%, about 30% won,
on deals the model did not learn from. Nothing here runs that held-out check
yet, so no screen, tool description or prompt may claim it. Add the check
first, then the word. Needs no Aito instance.
"""

import re

import booktest as bt

from company_ai.assistant import SYSTEM
from company_ai.config import REPO_ROOT
from company_ai.server import mcp

CLAIM = re.compile(r"\bcalibrated\b", re.IGNORECASE)
# user-facing files: what the dashboard, the README and the docs tell a reader
FILES = ["frontend/src/views.jsx", "README.md", *sorted(
    str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "docs").rglob("*.md"))]


async def test_no_calibration_claim(t: bt.TestCaseRun) -> None:
    found = []
    for tool in await mcp.list_tools():
        if CLAIM.search(tool.description or ""):
            found.append(f"MCP tool {tool.name}")
    if CLAIM.search(SYSTEM):
        found.append("assistant system prompt")
    for name in FILES:
        for n, line in enumerate((REPO_ROOT / name).read_text().splitlines(), 1):
            if CLAIM.search(line):
                found.append(f"{name}:{n}")
    t.h1("Surfaces claiming calibrated probabilities (must be none)")
    for where in found:
        t.tln(f"  {where}")
    if not found:
        t.tln("  none")
    assert not found, f"{len(found)} calibration claims with no held-out check: {found}"
