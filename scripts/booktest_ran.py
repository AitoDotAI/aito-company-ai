"""Fail a booktest run that executed nothing (td-20260926220026663014 b).

booktest exits 0 with "0/0 test succeeded" on an empty selection, and an
aborted run has printed a clean count after running nothing, so a green exit
alone does not mean tests passed. `./do test` pipes booktest's output here:
exit 1 unless the summary shows at least one test ran.

    uv run booktest book | tee out.txt; python scripts/booktest_ran.py out.txt
"""

import re
import sys

SUMMARY = re.compile(r"^(\d+)/(\d+) test ", re.MULTILINE)


def check(output: str) -> tuple[bool, str]:
    """(ran, why): whether the output's last summary line shows tests ran."""
    found = SUMMARY.findall(output)
    if not found:
        return False, "no booktest summary line: the run aborted before reporting"
    _, total = found[-1]
    if int(total) == 0:
        return False, "0 tests ran: the selection matched nothing"
    return True, f"{total} tests ran"


if __name__ == "__main__":
    with open(sys.argv[1], errors="replace") as f:
        ran, why = check(f.read())
    if not ran:
        print(f"✗ booktest: {why}. This is not a green.", file=sys.stderr)
        sys.exit(1)
