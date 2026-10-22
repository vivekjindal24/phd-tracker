# One image for Render (dev/test) and the self-hosted NAS stack (ARCHITECTURE.md §4).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

# Dependencies first (cached layer): read straight from pyproject.toml, no project build.
COPY pyproject.toml .
RUN uv pip install --system --no-cache -r pyproject.toml

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

RUN useradd --system --uid 10001 anveshan
USER anveshan

ENV PORT=8900
EXPOSE 8900
# Migrations run before serving. Single replica only: with more replicas, move
# `alembic upgrade head` into a release step so two instances never migrate at once.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
