"""Privacy gate (docs/06-privacy.md).

Two checks:
1. The committed seed CSVs are byte-identical to the deterministic
   generator's output, so they can contain nothing but the synthetic
   namespace.
2. No git-tracked file contains a phone-number- or email-shaped string.
"""

import importlib.util
import re
import subprocess
import tempfile
from pathlib import Path

import booktest as bt

from company_ai.config import REPO_ROOT

PHONE = re.compile(r"\+\d{7,}|\b\d{4,}[ -]\d{5,}\b")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _generator():
    spec = importlib.util.spec_from_file_location(
        "generate_seed", REPO_ROOT / "scripts" / "generate_seed.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_is_generator_output(t: bt.TestCaseRun) -> None:
    t.h1("Seed CSVs are byte-identical to the generator's output")
    gen = _generator()
    with tempfile.TemporaryDirectory() as tmp:
        # generate_all owns the sizes; keeping a second copy of that argument
        # list here made this gate fail whenever the seed was resized, which
        # reads as "the data is wrong" when nothing is wrong with the data.
        gen.generate_all(Path(tmp))
        files = ("rolodex.csv", "touches.csv", "sessions.csv", "materials.csv",
                 "channels.csv", "posts.csv", "todos.csv", "deals.csv",
                 "decisions.csv", "experiments.csv", "events.csv", "routines.csv",
                 "documents.csv", "AS_OF")
        for rel in [f"{d}/{f}" for d in ("seed", "seed_tiny") for f in files]:
            committed = (REPO_ROOT / "data" / rel).read_bytes()
            regenerated = (Path(tmp) / rel).read_bytes()
            assert committed == regenerated, (
                f"data/{rel} differs from generator output; "
                "regenerate with scripts/generate_seed.py or review the edit"
            )
            t.tln(f"data/{rel}: identical ({len(committed)} bytes)")


def test_no_contact_data_in_tracked_files(t: bt.TestCaseRun) -> None:
    t.h1("No phone- or email-shaped strings in tracked files")
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    leaks = []
    skipped_binary = []
    for name in tracked:
        try:
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # binary asset (e.g. a dashboard screenshot); cannot carry a
            # text-shaped phone/email leak. Screenshots show synthetic seed
            # data only — guaranteed by the seed-namespace gate above.
            skipped_binary.append(name)
            continue
        for pattern in (PHONE, EMAIL):
            for hit in pattern.findall(text):
                # RFC 2606 reserves example.{com,org,net} as placeholder domains
                # that can never be a real address — the users/assignees fixtures
                # (docs/27) need email-shaped values, and these are unmistakably
                # synthetic. The operator's real identity lives in env (gitignored),
                # never in a tracked file.
                low = hit.lower()
                if low.endswith(("@example.com", "@example.org", "@example.net")):
                    continue
                leaks.append(f"{name}: {hit}")
    for leak in leaks:
        t.tln(f"LEAK {leak}")
    assert not leaks, f"contact-shaped strings in tracked files: {leaks}"
    t.tln(f"no matches ({len(skipped_binary)} binary files skipped)")
