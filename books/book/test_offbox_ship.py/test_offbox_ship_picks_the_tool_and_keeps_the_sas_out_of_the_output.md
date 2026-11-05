# an Azure container with a SAS

exit 0
  called: azcopy copy <tmp>/offbox-2026-11-05T035000Z/* https://aitobackup.blob.core.windows.net/company-ai/offbox-2026-11-05T035000Z?<SAS> --recursive --log-level=ERROR
  output: offbox-ship: azcopy -> https://aitobackup.blob.core.windows.net/company-ai/offbox-2026-11-05T035000Z/ | azcopy copy <tmp>/offbox-2026-11-05T035000Z/* https://aitobackup.blob.core.windows.net/company-ai/offbox-2026-11-05T035000Z?<SAS> --recursive --log-level=ERROR

# a SAS given with its leading ?

exit 0
  called: azcopy copy <tmp>/offbox-2026-11-05T035000Z/* https://aitobackup.blob.core.windows.net/company-ai/offbox-2026-11-05T035000Z?<SAS> --recursive --log-level=ERROR
  output: offbox-ship: azcopy -> https://aitobackup.blob.core.windows.net/company-ai/offbox-2026-11-05T035000Z/ | azcopy copy <tmp>/offbox-2026-11-05T035000Z/* https://aitobackup.blob.core.windows.net/company-ai/offbox-2026-11-05T035000Z?<SAS> --recursive --log-level=ERROR

# an Azure container without a SAS

exit 2
  output: offbox-ship: https://aitobackup.blob.core.windows.net/company-ai is an Azure container but COMPANY_AI_OFFBOX_SAS is not set — refusing to run.

# a local path

exit 0
  called: rsync -a --mkpath <tmp>/offbox-2026-11-05T035000Z/ /mnt/backups/company-ai/offbox-2026-11-05T035000Z/
  output: offbox-ship: rsync -> /mnt/backups/company-ai/offbox-2026-11-05T035000Z/ | rsync -a --mkpath <tmp>/offbox-2026-11-05T035000Z/ /mnt/backups/company-ai/offbox-2026-11-05T035000Z/

# no destination

exit 2
  output: offbox-ship: COMPANY_AI_OFFBOX_DEST is not set — refusing to run.
