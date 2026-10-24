# Self-hosting Anveshan

One installation per university, on a Linux server or NAS with Docker and Docker
Compose. Seven containers: Postgres, Garage (file store), API, export, web,
Caddy (HTTPS) and cron (daily job + nightly backups). ARCHITECTURE.md §4 has the
design; this is the operator's checklist. Commands run from the repo root.

## Before you start

- Two DNS names pointing at the server, e.g. `phd.univ.ac.in` (the app) and
  `files.phd.univ.ac.in` (file downloads/uploads), with ports 80 and 443 open to
  them. Caddy gets and renews the certificates.
- Full-disk encryption on the data disk (SECURITY.md §8) and a second disk for
  backups.

## Install

```bash
cp deploy/.env.example deploy/.env      # fill in every value; secrets: the command above each
docker compose -f deploy/compose.prod.yml up -d --build
sh deploy/garage-init.sh                # once: file-store layout, bucket, API key
docker compose -f deploy/compose.prod.yml exec -e SEED_PASSWORD='<first password>' api \
  python -m app.seed --bootstrap --university "<University name>" --code <CODE> \
  --admin-email <admin@univ.ac.in> --admin-name "<Admin name>"
```

The root admin signs in at `https://<DOMAIN>` with that password and builds
the org tree in Settings. Check: `https://<DOMAIN>/api/v1/healthz` answers
`{"status":"ok"}`.

To trial the stack on a laptop: `SCHEME=http`, `DOMAIN=localhost`,
`FILES_DOMAIN=files.localhost`, and `DATA_DIR`/`BACKUP_DIR` in your home folder.

## Upgrade

```bash
git pull
docker compose -f deploy/compose.prod.yml up -d --build   # the API migrates on start
```

## Backups

Every night at 02:00 the cron container writes `BACKUP_DIR/db/anveshan-<date>.dump`
(kept `BACKUP_KEEP_DAYS` days) and copies every stored file into
`BACKUP_DIR/files/`. The daily job runs at 06:00. Both log to
`docker compose -f deploy/compose.prod.yml logs cron`; run either by hand with
`… exec cron run.sh backup` / `run.sh daily`.

## Restore

Test this once before go-live (SECURITY.md §8). On a fresh install (Install
steps up to `garage-init.sh`, skipping the bootstrap):

```bash
C="docker compose -f deploy/compose.prod.yml"
$C stop api cron
$C exec -T db pg_restore -U anveshan -d anveshan --clean --if-exists < /mnt/backup/anveshan/db/anveshan-<date>.dump
$C run --rm -v /mnt/backup/anveshan/files:/restore:ro cron \
  sh -c 'rclone copy /restore "store:$S3_BUCKET"'
$C start api cron
```
