#!/usr/bin/env bash
# Scheduler entry point for the daily aito.ai web analytics pull (docs/35).
#
# Pulls the last 3 complete UTC days from Amplitude's Export API into the
# web_sessions table. A re-pull replaces a day, so the overlap is free and a
# run missed while the machine was off is backfilled by the next one. The
# Amplitude keys live in the env file the operator placed; this script never
# reads or prints them. Kept tiny and self-locating like compact.sh.
#
#   ops/web-pull.sh                       # the last 3 days
#   ops/web-pull.sh --day 2026-11-01      # one day by hand
#
set -euo pipefail

export PATH="/run/current-system/sw/bin:${PATH:-}"
export NIX_PATH="${NIX_PATH:-nixpkgs=flake:nixpkgs:/nix/var/nix/profiles/per-user/root/channels}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COMPANY_AI_ENV="${COMPANY_AI_ENV:-.env.aito}"

cd "$REPO"
exec nix-shell "$REPO/shell.nix" --run "uv run company-ai pull-web $*"
