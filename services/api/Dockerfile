FROM python:3.12-slim

WORKDIR /srv
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
RUN pip install --no-cache-dir -e .

EXPOSE 8000
# single-instance free tier: migrate then serve (move to a deploy step if replicas > 1)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]