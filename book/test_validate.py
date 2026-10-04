"""Checking a whole data directory before any of it loads (validate.py).

Rule 3 raises on the first surprising row. For someone bringing their own
export that means fix one row, rerun, hit the next — and most of the hundreds
of failures are the same one or two problems. These tests pin the three things
that make the first contact bearable: every problem in one pass, grouped into
the handful of fixes it really is, and still nothing loaded.
"""

import csv
import shutil
import tempfile
from pathlib import Path

import booktest as bt

from company_ai import loaders, validate
from company_ai.config import SEED_DIR


def _export(edits) -> Path:
    """A copy of three seed files with problems planted, like a real first export."""
    d = Path(tempfile.mkdtemp())
    for name in ("rolodex.csv", "deals.csv", "todos.csv"):
        shutil.copy(SEED_DIR / name, d / name)
    for name, fn in edits.items():
        rows = list(csv.DictReader(open(d / name)))
        rows = fn(rows)
        with open(d / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
    return d


def _contacts(rows):
    for i, r in enumerate(rows):
        r["segment"] = ["public-sector", "retail"][i % 2]   # their taxonomy
    rows[7]["tier"] = "strategic"
    rows[12]["created"] = "12.03.2026"                     # a local-format date
    rows.append(dict(rows[3]))                             # an exported duplicate
    return rows


def _todos(rows):
    rows[5]["area"] = "delivery"                           # not a dashboard area
    return rows


def test_the_shipped_seed_is_clean(t: bt.TestCaseRun) -> None:
    report = validate.validate_dir(SEED_DIR)
    t.tln(report.render())


def test_every_problem_in_one_pass_grouped_into_fixes(t: bt.TestCaseRun) -> None:
    d = _export({"rolodex.csv": _contacts, "todos.csv": _todos})
    report = validate.validate_dir(d)
    t.h1("a first export, problems planted")
    t.tln(report.render())
    t.h1("what that means for the person fixing it")
    t.tln(f"distinct problems: {len(report.problems)}   rows affected: {report.bad_rows}")
    # each of these sat BEHIND the segment failure on its row; a parser that
    # stops at the first check would only show them on a later run
    for needle in ("unknown tier", "not an ISO date", "duplicate contact_id"):
        t.tln(f"surfaced in the first pass — {needle}: "
              f"{any(needle in p.message for p in report.problems)}")
    shutil.rmtree(d)


def test_load_all_refuses_and_writes_nothing(t: bt.TestCaseRun) -> None:
    d = _export({"rolodex.csv": _contacts})
    t.h1("load_all validates before it touches an instance")
    try:
        loaders.load_all(None, d)     # no client: it must fail before using one
        t.tln("loaded (WRONG)")
    except validate.DataProblems as e:
        t.tln("refused with the full report, nothing written:")
        t.tln(f"  still an AssertionError (rule 3 handlers catch it): "
              f"{isinstance(e, AssertionError)}")
        t.tln(f"  report lists {str(e).count('unknown segment')} segment problem group(s)")
    shutil.rmtree(d)


def test_collecting_never_leaks_into_a_real_load(t: bt.TestCaseRun) -> None:
    t.h1("outside validate, the first surprise still raises — rule 3 unchanged")
    row = next(iter(csv.DictReader(open(SEED_DIR / "rolodex.csv"))))
    row["segment"] = "public-sector"
    try:
        loaders.parse_rolodex_row(dict(row))
        t.tln("accepted (WRONG)")
    except AssertionError as e:
        t.tln(f"raised: {str(e).split(';')[0]}")
        t.tln(f"with the row attached: {'offending row' in str(e)}")
