# Self-hosting Anveshan

One installation per university, on a Linux server or NAS with Docker and Docker
Compose. Eight containers: Postgres, Garage (file store), ClamAV (virus scanner),
API, export, web, Caddy (HTTPS) and cron (daily job + nightly backups). ARCHITECTURE.md §4 has the
design; this is the operator's checklist. Commands run from the repo root.

## Before you start

- Two DNS names pointing at the server, e.g. `phd.univ.ac.in` (the app) and
  `files.phd.univ.ac.in` (file downloads/uploads), with ports 80 and 443 open to
  them. Caddy gets and renews the certificates. No public address or open ports?
  See Behind a Cloudflare Tunnel below.
- Memory: at least 3 GB of RAM; 8 GB recommended for a university. The virus scanner
  alone holds about 1 GB (its signatures), kept lean so it never doubles while it
  updates them — scanning pauses for about a minute instead. Its first start
  downloads about 300 MB of signatures; until then uploads are refused, not let
  through. `MAX_UPLOAD_MB` above 400 also needs `CLAMD_CONF_MaxScanSize` raised on
  the `clamav` service.
- Full-disk encryption on the data disk and on the backup disk (SECURITY.md §8):
  the local backups are plain files.
- Recommended: S3-compatible storage somewhere else for the encrypted off-site
  copy (Backups below).

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

Uploaded files live in `DATA_DIR/garage/data` unless `GARAGE_DATA_DIR` points
elsewhere, e.g. a larger disk; size `GARAGE_CAPACITY` to that disk.

## Behind a Cloudflare Tunnel

For a server that cannot take incoming connections (no public address, no ports
80/443). `cloudflared` dials out to Cloudflare, which ends TLS and passes the
requests to Caddy over plain http; no port is published on the host.

1. In Cloudflare Zero Trust, create a tunnel (Networks → Tunnels, type
   cloudflared) and add two public hostnames, `DOMAIN` and `FILES_DOMAIN`, both
   to the service `http://caddy:80`. Use names one level below your zone
   (`phd.example.org`, `phd-files.example.org`): the free certificate does not
   cover deeper names.
2. Add a Cache Rule that bypasses the cache for `FILES_DOMAIN`: presigned
   links end in the real file name, so Cloudflare would otherwise cache files
   and serve them past the link's expiry.
3. In `deploy/.env`: `SCHEME=https`, the tunnel's token in `TUNNEL_TOKEN`, and
   `MAX_UPLOAD_MB` below Cloudflare's request limit (100 MB on the free plan).
4. Add `-f deploy/compose.tunnel.yml` after `-f deploy/compose.prod.yml` on
   every compose command in this file (`garage-init.sh` works unchanged):

```bash
C="docker compose -f deploy/compose.prod.yml -f deploy/compose.tunnel.yml --env-file deploy/.env"
$C up -d --build
```

The public URLs stay https; inside, the API reaches the file store through
Cloudflare at `https://<FILES_DOMAIN>` like browsers do, so presigned
signatures still match.

To keep an old name working, e.g. after moving `DOMAIN`, add a tunnel hostname
for it and a site block in `deploy/sites/<name>.caddy` (not committed; Caddy
imports every `*.caddy` there):

```
{$LISTEN_SCHEME}://old.example.org {
	redir {$SCHEME}://{$DOMAIN}{uri} permanent
}
```

## Upgrade

```bash
git pull
docker compose -f deploy/compose.prod.yml up -d --build   # the API migrates on start
```

## Capacity test

How many people at once this server serves. `deploy/loadtest.py` signs in the demo
university's accounts with their `SEED_PASSWORD`. Simulated
people then click through the busiest pages, each reading for 5–15 s between clicks.
The test holds 10, 25, 50, 100, 150 and 200 people for a minute each and stops at the
first stage where pages slow past 1 s or anything fails. It runs inside the API
container and goes through Caddy, like a browser. It only signs in and marks
notifications seen. It needs the demo data, so run it on a trial install (such as the
demo server), not a live one.

```bash
read -rs LOAD_PASSWORD   # type the demo password; it is not shown
docker compose -f deploy/compose.prod.yml --env-file deploy/.env exec -T \
  -e LOAD_PASSWORD="$LOAD_PASSWORD" api python - < deploy/loadtest.py
```

Behind the tunnel, add `-f deploy/compose.tunnel.yml` after `compose.prod.yml`. Not
behind it, add `-e LOAD_URL=https://<the app's address>` (Caddy serves only https then).
`LOAD_STAGES=50,100,300` (after `-e`) sets other stages, and `LOAD_SECONDS` sets the
length of each. What the numbers mean: docs/THINGS_TO_KNOW.md, "How many people at once".

## Backups

Every night at 02:00 the cron container writes `BACKUP_DIR/db/anveshan-<date>.dump`
(kept `BACKUP_KEEP_DAYS` days) and copies every stored file into
`BACKUP_DIR/files/`. The daily job runs at 06:00. Both log to
`docker compose -f deploy/compose.prod.yml logs cron`; run either by hand with
`… exec cron run.sh backup` / `run.sh daily`.

### Off-site copy

A second disk in the same building does not survive a fire or a theft. Fill the
`OFFSITE_*` group in `deploy/.env` to also send every nightly backup to
S3-compatible storage somewhere else, then `up -d` again. The copy is encrypted
on this server with `OFFSITE_PASSPHRASE` before it leaves, file names included,
so the storage provider holds nothing readable. Database dumps older than
`BACKUP_KEEP_DAYS` are removed there too; files are kept.

Keep the passphrase somewhere other than this server (the registrar's safe, a
password manager): without it the off-site copy cannot be read. Keep `AUDIT_KEY`
there too, and never change it: it seals the audit trail, and a restored
database is checked with it (SECURITY.md §6). The backup log
says each night whether the off-site copy was sent, or that it is not
configured.

To restore after losing the server and the backup disk, install afresh with
the same `OFFSITE_*` values, run `… exec cron run.sh fetch` to bring the copy
back into `BACKUP_DIR`, then follow Restore below.

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
