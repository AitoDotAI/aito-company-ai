#!/usr/bin/env bash
# Scheduler entry point for compacting the Aito tables (hourly).
#
# Writes no longer flush (td-20261014123607349120): each `_modify` leaves a
# pending delete plus a one-row segment, and listings slow 2-5x as those pile
# up. An hourly compaction bounds the pile without any user call paying for it.
# Kept tiny and self-locating like backup.sh; enters the same Nix environment.
#
#   ops/compact.sh
#
set -euo pipefail

export PATH="/run/current-system/sw/bin:${PATH:-}"
export NIX_PATH="${NIX_PATH:-nixpkgs=flake:nixpkgs:/nix/var/nix/profiles/per-user/root/channels}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COMPANY_AI_ENV="${COMPANY_AI_ENV:-.env.aito}"

cd "$REPO"
exec nix-shell "$REPO/shell.nix" --run "uv run company-ai compact"
