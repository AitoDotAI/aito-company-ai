#!/usr/bin/env bash
# Ship one staged off-box dump to COMPANY_AI_OFFBOX_DEST (docs/21). Called by
# ops/backup-offbox.sh; kept apart so it can be tested with stub tools.
#
#   ops/offbox-ship.sh <staging dir> <name>
#
# An https:// destination is an Azure blob container: the dump is uploaded
# with azcopy under <container>/<name>/, authorised by COMPANY_AI_OFFBOX_SAS, a
# create+write SAS the operator places (no delete or list, so this machine
# cannot wipe the history; without read, azcopy must not check lengths or
# ask before overwriting, hence the flags below). The SAS is never printed:
# azcopy's output goes through a filter that blanks it. Anything else is an
# rsync destination (a local path, or user@host:/path over ssh).
#
# AZCOPY / RSYNC override the tools (the booktest passes stubs).
set -euo pipefail

staging="${1:?staging dir}"
name="${2:?name}"
dest="${COMPANY_AI_OFFBOX_DEST:-}"

if [ -z "$dest" ]; then
  echo "offbox-ship: COMPANY_AI_OFFBOX_DEST is not set — refusing to run." >&2
  exit 2
fi

case "$dest" in
  https://*)
    sas="${COMPANY_AI_OFFBOX_SAS:-}"
    sas="${sas#\?}"
    if [ -z "$sas" ]; then
      echo "offbox-ship: $dest is an Azure container but COMPANY_AI_OFFBOX_SAS is not set — refusing to run." >&2
      exit 2
    fi
    # azcopy keeps job plans and logs under ~/.azcopy, and a plan can hold the
    # full URL with the SAS: keep them in a private temp dir, removed on exit
    work="$(mktemp -d)"
    trap 'rm -rf "$work"' EXIT
    export AZCOPY_JOB_PLAN_LOCATION="$work/plans" AZCOPY_LOG_LOCATION="$work/logs"
    echo "offbox-ship: azcopy -> ${dest%/}/$name/"
    "${AZCOPY:-azcopy}" copy "$staging/*" "${dest%/}/$name?$sas" --recursive \
      --overwrite=true --check-length=false --put-md5 --log-level=ERROR 2>&1 \
      | sed -e "s|$sas|<SAS>|g" -e 's|sig=[^&[:space:]]*|sig=<redacted>|g'
    ;;
  *)
    echo "offbox-ship: rsync -> $dest/$name/"
    "${RSYNC:-rsync}" -a --mkpath "$staging/" "$dest/$name/"
    ;;
esac
