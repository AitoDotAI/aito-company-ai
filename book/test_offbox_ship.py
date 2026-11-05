"""Shipping the off-box backup (docs/21): rsync for a path or ssh
destination, azcopy for an https:// Azure blob container.

ops/offbox-ship.sh is run with stub rsync and azcopy that only record their
arguments, so no file leaves the machine. The SAS token is a secret placed
by the operator: it must reach azcopy but never the script's output.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import booktest as bt

from company_ai.config import REPO_ROOT

SHIP = REPO_ROOT / "ops" / "offbox-ship.sh"
SAS = "sv=2026-01-01&sp=cw&sig=STUBSECRETSTUBSECRET"


def _run(dest: str | None, sas: str | None) -> tuple[int, str, list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        staging = tmp / "offbox-2026-11-05T035000Z"
        staging.mkdir()
        (staging / "todos.csv").write_text("todo_id\n")
        calls = tmp / "calls"
        for tool in ("azcopy", "rsync"):
            stub = tmp / tool
            # each stub also echoes its arguments, as a failing azcopy prints its URL
            # and azcopy leaves a job plan holding the URL, as the real one does
            plan = ('mkdir -p "$AZCOPY_JOB_PLAN_LOCATION" && echo "$AZCOPY_JOB_PLAN_LOCATION" '
                    f'>> "{tmp}/plandirs" && echo "$*" > "$AZCOPY_JOB_PLAN_LOCATION/job.plan"\n'
                    if tool == "azcopy" else "")
            stub.write_text(f'#!/usr/bin/env bash\necho "{tool} $*" >> "{calls}"\necho "{tool} $*"\n{plan}')
            stub.chmod(0o755)
        env = {k: v for k, v in os.environ.items() if not k.startswith("COMPANY_AI_OFFBOX")}
        env.update({"AZCOPY": str(tmp / "azcopy"), "RSYNC": str(tmp / "rsync")})
        if dest is not None:
            env["COMPANY_AI_OFFBOX_DEST"] = dest
        if sas is not None:
            env["COMPANY_AI_OFFBOX_SAS"] = sas
        done = subprocess.run([str(SHIP), str(staging), staging.name], env=env,
                              capture_output=True, text=True)
        recorded = calls.read_text().splitlines() if calls.exists() else []
        plandirs = tmp / "plandirs"
        for d in (plandirs.read_text().split() if plandirs.exists() else []):
            assert not Path(d).exists(), f"azcopy's job plan was left behind in {d}"
            assert not d.startswith(str(Path.home())), f"job plans under the home dir: {d}"
        out = (done.stdout + done.stderr).replace(str(tmp), "<tmp>")
        return done.returncode, out, [c.replace(str(tmp), "<tmp>") for c in recorded]


def test_offbox_ship_picks_the_tool_and_keeps_the_sas_out_of_the_output(t: bt.TestCaseRun) -> None:
    blob = "https://aitobackup.blob.core.windows.net/company-ai"
    cases = [
        ("an Azure container with a SAS", blob, SAS),
        ("a SAS given with its leading ?", blob, "?" + SAS),
        ("an Azure container without a SAS", blob, None),
        ("a local path", "/mnt/backups/company-ai", None),
        ("no destination", None, None),
    ]
    got = {}
    for name, dest, sas in cases:
        code, out, calls = _run(dest, sas)
        t.h1(name)
        t.tln(f"exit {code}")
        shown = [c.replace(SAS, "<SAS>") for c in calls]
        for c in shown:
            t.tln(f"  called: {c}")
        t.tln("  output: " + " | ".join(line for line in out.splitlines() if line))
        assert "STUBSECRET" not in out, f"{name}: the SAS reached the output"
        got[name] = (code, [c.split()[0] for c in calls])
        if dest == blob and sas:
            assert calls == [f"azcopy copy <tmp>/offbox-2026-11-05T035000Z/* "
                             f"{blob}/offbox-2026-11-05T035000Z?{SAS} --recursive "
                             f"--overwrite=true --check-length=false --put-md5 "
                             f"--log-level=ERROR"], calls
    assert got == {
        "an Azure container with a SAS": (0, ["azcopy"]),
        "a SAS given with its leading ?": (0, ["azcopy"]),
        "an Azure container without a SAS": (2, []),
        "a local path": (0, ["rsync"]),
        "no destination": (2, []),
    }, got
