#!/bin/sh
# run.sh daily  — the API's daily job (ARCHITECTURE.md §10)
# run.sh backup — nightly pg_dump + file-store copy to the backup disk, then an encrypted
#                 copy off-site when OFFSITE_REMOTE is set (SECURITY.md §8)
# run.sh fetch  — bring the off-site copy back into /backup, before a restore
set -eu
. /etc/anveshan.env

# The off-site copy goes through rclone's crypt layer: file contents and names are encrypted
# on this server with OFFSITE_PASSPHRASE, so the storage provider holds nothing readable.
# Lose the passphrase and the off-site copy is lost with it.
vault() {
  : "${OFFSITE_PASSPHRASE:?OFFSITE_REMOTE is set, so OFFSITE_PASSPHRASE must be too}"
  RCLONE_CONFIG_VAULT_TYPE=crypt
  RCLONE_CONFIG_VAULT_REMOTE=$OFFSITE_REMOTE
  RCLONE_CONFIG_VAULT_PASSWORD=$(rclone obscure "$OFFSITE_PASSPHRASE")
  export RCLONE_CONFIG_VAULT_TYPE RCLONE_CONFIG_VAULT_REMOTE RCLONE_CONFIG_VAULT_PASSWORD
}

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
  if [ -n "${OFFSITE_REMOTE:-}" ]; then
    vault
    rclone copy /backup/db vault:db
    rclone copy /backup/files vault:files
    rclone delete --min-age "${BACKUP_KEEP_DAYS}d" vault:db
    echo "off-site ok: encrypted copy sent"
  else
    echo "off-site copy is not configured (OFFSITE_REMOTE): this backup exists only on this site"
  fi
  ;;
fetch)
  : "${OFFSITE_REMOTE:?set OFFSITE_REMOTE and OFFSITE_PASSPHRASE to fetch the off-site copy}"
  vault
  mkdir -p /backup/db /backup/files
  # The whole vault in one go: a university with no uploads yet has no files/ folder there.
  rclone copy vault: /backup
  echo "fetched the off-site copy into /backup"
  ;;
*)
  echo "usage: run.sh daily|backup|fetch" >&2
  exit 2
  ;;
esac
