#!/usr/bin/env bash
# Scheduler entry point for the weekly week-prep composer.
#
# Kept tiny and self-locating so any scheduler (systemd timer, cron, or a
# cloud trigger on this host) can call it with just a prompt + mode and needs
# no project knowledge. It enters the same Nix environment `./do` uses, so the
# uv/python toolchain and the PYTHONPATH fix come for free.
#
#   ops/board-run.sh week-prep.md prepare
#   ops/board-run.sh week-prep.md plan
#
# Targets the real instance by default (.env.aito); override COMPANY_AI_ENV to
# point elsewhere. The composer needs COMPANY_AI_LLM_API_KEY set in that env
# file — without it the run fails loudly (by design), it does not compose
# nothing.
set -euo pipefail

# stable NixOS system path first, so even coreutils (dirname) and nix-shell are
# found under the minimal PATH a systemd --user service starts with
export PATH="/run/current-system/sw/bin:${PATH:-}"
# nix-shell needs the channel search path, also absent in a minimal env
export NIX_PATH="${NIX_PATH:-nixpkgs=flake:nixpkgs:/nix/var/nix/profiles/per-user/root/channels}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COMPANY_AI_ENV="${COMPANY_AI_ENV:-.env.aito}"

prompt="${1:?usage: board-run.sh <prompt.md> <mode>}"
mode="${2:?usage: board-run.sh <prompt.md> <mode>}"

cd "$REPO"
exec nix-shell "$REPO/shell.nix" --run "uv run company-ai board-run '$prompt' --mode '$mode'"
