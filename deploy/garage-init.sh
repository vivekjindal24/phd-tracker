#!/bin/sh
# One-time file-store setup after the first `up`: lay out this single node, create the
# bucket and import the API's key from deploy/.env. Re-running fails loudly at the
# first step already done. GARAGE overrides how the CLI is reached (CI uses docker exec).
set -eu
cd "$(dirname "$0")/.."
ENV_FILE=${ENV_FILE:-deploy/.env}
GARAGE=${GARAGE:-docker compose -f deploy/compose.prod.yml --env-file $ENV_FILE exec -T garage /garage}

setting() {
  value=$(printenv "$1" || sed -n "s/^$1=//p" "$ENV_FILE" 2>/dev/null | tail -n1)
  [ -n "$value" ] || { echo "garage-init: $1 is not set" >&2; exit 1; }
  printf '%s' "$value"
}
bucket=$(setting S3_BUCKET)
key_id=$(setting S3_ACCESS_KEY_ID)
secret=$(setting S3_SECRET_ACCESS_KEY)
capacity=$(setting GARAGE_CAPACITY)

# The daemon may still be starting right after `up`.
for _ in $(seq 30); do $GARAGE status >/dev/null 2>&1 && break; sleep 1; done
node=$($GARAGE node id -q | cut -d@ -f1)
$GARAGE layout assign -z dc1 -c "$capacity" "$node"
$GARAGE layout apply --version 1
$GARAGE bucket create "$bucket"
$GARAGE key import --yes -n anveshan-api "$key_id" "$secret"
$GARAGE bucket allow --read --write --owner "$bucket" --key "$key_id"
echo "garage-init: bucket $bucket ready"
