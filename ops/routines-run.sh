#!/usr/bin/env bash
# Scheduler entry point for auto-running due routines (docs/18).
#
# Kept tiny and self-locating so any scheduler (systemd timer, cron, or a
# cloud trigger on this host) can call it with no arguments. It enters the same
# Nix environment `./do` uses, so the uv/python toolchain comes for free.
#
#   ops/routines-run.sh                 # run every DUE routine
#   ops/routines-run.sh rt-outreach     # limit to one routine id (--only)
#
# Targets the real instance by default (.env.aito); override COMPANY_AI_ENV to
# point elsewhere. Uses the LLM (COMPANY_AI_LLM_API_KEY must be set in that env
# file) — without it the run fails loudly (by design). Each routine executes
# through the assistant's bounded, read-only tool loop and lands its output as a
# journal entry; it prepares and narrates, it does not act (no outbound).
set -euo pipefail

export PATH="/run/current-system/sw/bin:${PATH:-}"
export NIX_PATH="${NIX_PATH:-nixpkgs=flake:nixpkgs:/nix/var/nix/profiles/per-user/root/channels}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COMPANY_AI_ENV="${COMPANY_AI_ENV:-.env.aito}"

only="${1:-}"

cd "$REPO"
if [ -n "$only" ]; then
  exec nix-shell "$REPO/shell.nix" --run "uv run company-ai routines-run --only '$only'"
else
  exec nix-shell "$REPO/shell.nix" --run "uv run company-ai routines-run"
fi
