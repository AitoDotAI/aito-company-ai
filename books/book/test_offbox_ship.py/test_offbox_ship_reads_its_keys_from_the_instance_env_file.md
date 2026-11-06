# Keys only in the env file

exit 0
  called: azcopy copy <tmp>/offbox-2026-11-05T035000Z/* https://aitobackup.blob.core.windows.net/company-ai/offbox-2026-11-05T035000Z?<SAS> --recursive --overwrite=true --check-length=false --put-md5 --log-level=ERROR

# An environment value wins over the file

exit 0, tool rsync
