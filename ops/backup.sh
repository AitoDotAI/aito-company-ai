#!/usr/bin/env bash
# Scheduler entry point for database backups (Aito env snapshots, docs/21).
#
# Kept tiny and self-locating so any scheduler (systemd timer, cron, or a cloud
# trigger on this host) can call it with just a kind and needs no project
# knowledge. Enters the same Nix environment `./do` uses.
#
#   ops/backup.sh daily     # keep the last 7
#   ops/backup.sh tx        # keep the last 16 (before risky write-bursts)
#
# Targets the real instance by default (.env.aito); override COMPANY_AI_ENV to
# point elsewhere. A snapshot is copy-on-write — milliseconds, ~no disk.
set -euo pipefail

export PATH="/run/current-system/sw/bin:${PATH:-}"
export NIX_PATH="${NIX_PATH:-nixpkgs=flake:nixpkgs:/nix/var/nix/profiles/per-user/root/channels}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COMPANY_AI_ENV="${COMPANY_AI_ENV:-.env.aito}"

kind="${1:-daily}"

cd "$REPO"
exec nix-shell "$REPO/shell.nix" --run "uv run company-ai backup --kind '$kind'"
