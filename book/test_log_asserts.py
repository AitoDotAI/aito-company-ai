"""log.py's input checks survive `python -O` (P3). They raised with bare
`assert`, which -O strips, so a bad row would be written instead of refused
(rule 3). They now raise AssertionError explicitly, so callers that catch it
(the MCP and API guards) are unchanged. No Aito instance needed."""

import ast
import subprocess
import sys
from pathlib import Path

import booktest as bt

LOG = Path(__file__).resolve().parents[1] / "src" / "company_ai" / "log.py"

PROBE = """
from company_ai import log
try:
    log.log_decision(None, "no-such-type", {}, "x", 0.5, "accept")
    print("not refused")
except AssertionError as e:
    print("AssertionError:", e)
except Exception as e:
    print("refused with the wrong error:", type(e).__name__)
"""


def test_input_checks_survive_python_O(t: bt.TestCaseRun) -> None:
    t.h1("A bad decision_type under python -O")
    out = subprocess.run([sys.executable, "-O", "-c", PROBE], capture_output=True, text=True, check=True)
    t.tln(f"  {out.stdout.strip()}")
    assert out.stdout.startswith("AssertionError: unknown decision_type"), out.stdout + out.stderr


def test_log_has_no_bare_asserts(t: bt.TestCaseRun) -> None:
    left = [n.lineno for n in ast.walk(ast.parse(LOG.read_text())) if isinstance(n, ast.Assert)]
    t.h1("Bare assert statements left in log.py")
    t.tln(f"  {len(left)}")
    assert not left, f"bare asserts at lines {left}"
