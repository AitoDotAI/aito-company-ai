#!/usr/bin/env bash
# Off-box backup — the second plane (docs/21).
#
# ops/backup.sh makes Aito *env snapshots*: copy-on-write branches INSIDE the
# instance. They are the cheap undo for a bad write, but they live on the same
# box and die with it. This script is the other plane: a portable CSV dump of
# every table (`export-all`, docs/06) pushed OFF the machine.
#
#   COMPANY_AI_OFFBOX_DEST=/mnt/backups/company-ai        ops/backup-offbox.sh
#   COMPANY_AI_OFFBOX_DEST=user@host:/srv/backups/company-ai ops/backup-offbox.sh
#
# Any rsync-addressable destination works (local path, remote over ssh). The
# dump is the REAL dataset, so the destination is operator-configured and never
# defaulted: with no destination this refuses to run rather than quietly leave
# the dump on the box it is meant to survive (rule 3 — no silent data handling).
#
# Requires rsync >= 3.2.3 (--mkpath, to create a missing destination path) and
# GNU coreutils (the rotation uses `head -n -N`). Both hold on the NixOS box
# this runs on; on anything older, pre-create the destination and drop the flag.
set -euo pipefail

export PATH="/run/current-system/sw/bin:${PATH:-}"
export NIX_PATH="${NIX_PATH:-nixpkgs=flake:nixpkgs:/nix/var/nix/profiles/per-user/root/channels}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COMPANY_AI_ENV="${COMPANY_AI_ENV:-.env.aito}"

if [ -z "${COMPANY_AI_OFFBOX_DEST:-}" ]; then
  echo "backup-offbox: COMPANY_AI_OFFBOX_DEST is not set — refusing to run." >&2
  echo "  An on-box-only copy is not an off-box backup. Set it to an rsync" >&2
  echo "  destination, e.g. /mnt/backups/company-ai or user@host:/srv/backups." >&2
  exit 2
fi

stamp="$(date -u +%Y-%m-%dT%H%M%SZ)"
staging="${COMPANY_AI_OFFBOX_STAGING:-$REPO/.backups}/offbox-$stamp"
keep="${COMPANY_AI_OFFBOX_KEEP:-3}"        # local staging copies to retain

cd "$REPO"
mkdir -p "$staging"
echo "backup-offbox: exporting every table -> $staging"
nix-shell "$REPO/shell.nix" --run "uv run company-ai export-all --dir '$staging'"

# An empty or partial export must fail loudly: shipping it off-box would
# overwrite nothing, but it WOULD look like a good backup in the listing.
count="$(find "$staging" -maxdepth 1 -name '*.csv' | wc -l | tr -d ' ')"
if [ "$count" -eq 0 ]; then
  echo "backup-offbox: export produced no CSVs — aborting, nothing shipped." >&2
  exit 1
fi
echo "backup-offbox: $count tables exported"

echo "backup-offbox: syncing -> $COMPANY_AI_OFFBOX_DEST/offbox-$stamp"
rsync -a --mkpath "$staging/" "$COMPANY_AI_OFFBOX_DEST/offbox-$stamp/"

# rotate local staging only; the off-box side is retained by whatever policy
# the destination has (that is deliberately not this script's business).
ls -1d "${COMPANY_AI_OFFBOX_STAGING:-$REPO/.backups}"/offbox-* 2>/dev/null \
  | sort | head -n "-$keep" | while read -r old; do
      echo "backup-offbox: rotating out local $old"
      rm -rf "$old"
    done

echo "backup-offbox: done ($count tables, $stamp)"
