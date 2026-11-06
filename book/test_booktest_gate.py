"""A booktest run that ran nothing is an error, not a green
(td-20260926220026663014 part b).

booktest exits 0 and prints "0/0 test succeeded" when the selection is empty,
and an aborted run once printed a clean count after executing nothing. `./do
test` passes booktest's output through scripts/booktest_ran.py, which fails
the run unless at least one test ran.
"""

import importlib.util

import booktest as bt

from company_ai.config import REPO_ROOT


def _gate():
    spec = importlib.util.spec_from_file_location(
        "booktest_ran", REPO_ROOT / "scripts" / "booktest_ran.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_run_of_zero_tests_fails(t: bt.TestCaseRun) -> None:
    gate = _gate()
    cases = {
        "a green run": ("# test results:\n\n30/30 test succeeded in 61522 ms\n", True),
        "a run with diffs": ("2/38 test 2 differed in 58725 ms:\n  book/x.py::y - DIFF\n", True),
        "a run with failures": ("5/8 test 5 failed in 16402 ms:\n", True),
        "an empty selection": ("# test results:\n\n\n0/0 test succeeded in 5 ms\n", False),
        "an aborted run, no summary": ("Invalid JSON on line 3 of books/.out/cases.ndjson\n", False),
        "nothing at all": ("", False),
    }
    t.h1("Does the output show that tests ran?")
    got = {}
    for name, (output, want) in cases.items():
        ran, why = gate.check(output)
        got[name] = ran
        t.tln(f"{name}: ran={ran} ({why})")
    assert got == {name: want for name, (_, want) in cases.items()}, got


def test_a_second_run_in_the_same_checkout_is_refused(t: bt.TestCaseRun) -> None:
    """td-20260926220026663014 (a): `./do test` holds a lock on books/.out
    for its whole run, and a second run in the same checkout is refused
    before booktest starts. Under `./do test` the parent already holds the
    lock; under a bare `booktest`, this test takes it itself."""
    import fcntl
    import subprocess
    import time
    lock = REPO_ROOT / "books" / ".out" / ".run-lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as handle:
        try:                          # under a bare booktest: take it ourselves
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:       # under ./do test: the parent run holds it
            pass
        started = time.monotonic()
        done = subprocess.run([str(REPO_ROOT / "do"), "test", "skip:book"], cwd=REPO_ROOT,
                              capture_output=True, text=True, timeout=60)
        took = time.monotonic() - started
    t.h1("A second ./do test while the lock is held")
    t.tln(f"  exit {done.returncode}, refused at once: {took < 10}")
    t.tln(f"  {done.stderr.strip().splitlines()[-1] if done.stderr.strip() else '(no message)'}")
    assert done.returncode != 0 and "another ./do test is running" in done.stderr, done.stderr
