#!/usr/bin/env bash
# Local API with your private settings (~/.config/anveshan/dev.env, never in git).
set -euo pipefail
cd "$(dirname "$0")"
set -a
# shellcheck disable=SC1090
source "${ANVESHAN_ENV:-$HOME/.config/anveshan/dev.env}"
set +a
export JWT_SECRET="${JWT_SECRET:-dev-secret-0123456789abcdef0123456789abcdef}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000}"
find . -name '._*' -delete  # exFAT junk breaks alembic
~/.venvs/anveshan-api/bin/alembic upgrade head
exec ~/.venvs/anveshan-api/bin/uvicorn app.main:app --port 8900 --reload
