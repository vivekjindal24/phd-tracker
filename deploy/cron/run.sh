#!/bin/sh
# run.sh daily  — the API's daily job (ARCHITECTURE.md §10)
# run.sh backup — nightly pg_dump + file-store copy to the backup disk (SECURITY.md §8)
set -eu
. /etc/anveshan.env

case "${1:-}" in
daily)
  curl -fsS --retry 3 -X POST -H "X-Cron-Secret: $CRON_SECRET" \
    http://api:8900/api/v1/internal/cron/daily
  echo
  ;;
backup)
  mkdir -p /backup/db /backup/files
  dump="/backup/db/anveshan-$(date +%F).dump"
  pg_dump --format=custom --file="$dump.part"
  mv "$dump.part" "$dump"
  find /backup/db -name 'anveshan-*.dump' -mtime +"$BACKUP_KEEP_DAYS" -delete
  # copy, not sync: an object removed from the store stays in the backup, so any
  # retained dump can still be restored with all of its files.
  rclone copy "store:$S3_BUCKET" /backup/files
  echo "backup ok: $dump"
  ;;
*)
  echo "usage: run.sh daily|backup" >&2
  exit 2
  ;;
esac
