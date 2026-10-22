"""Tests run against the real Alembic DDL on a scratch database (TESTING.md §2)."""

import os
import subprocess
import sys
from pathlib import Path


def _load_private_env() -> None:
    """Fill variables the shell didn't set from the private dev file (never in git)."""
    path = Path(os.environ.get("ANVESHAN_ENV", Path.home() / ".config/anveshan/dev.env"))
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        name, sep, value = line.partition("=")
        if sep and not name.lstrip().startswith("#"):
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]  # shell-quoted (values containing & etc.)
            os.environ.setdefault(name.strip(), value)


_load_private_env()

# Tests TRUNCATE every table: never let them touch a non-test database.
_TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://localhost:5432/anveshan_test")
if not _TEST_DB.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
    raise RuntimeError(f"refusing to run tests against a non-*_test database: {_TEST_DB}")
os.environ["DATABASE_URL"] = _TEST_DB
# Files go to the test bucket only.
_TEST_BUCKET = os.environ.get("S3_TEST_BUCKET", "")
if not _TEST_BUCKET.endswith("-test"):
    raise RuntimeError("set S3_TEST_BUCKET to a *-test bucket (see ~/.config/anveshan/dev.env)")
os.environ["S3_BUCKET"] = _TEST_BUCKET
# Never send real email from tests; email tests capture messages explicitly.
for _smtp in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "MAIL_FROM"):
    os.environ.pop(_smtp, None)
os.environ.setdefault("JWT_SECRET", "test-secret-0123456789abcdef0123456789")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import insert, text  # noqa: E402

from app.auth.service import create_access_token  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.enums import DEFAULT_CHAINS, MODULE_KEYS  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ApprovalChain, Module  # noqa: E402
from tests.world import World, build_world  # noqa: E402

API_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def migrated() -> None:
    for junk in API_DIR.rglob("._*"):  # exFAT AppleDouble files break alembic
        junk.unlink(missing_ok=True)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=API_DIR, check=True)


@pytest.fixture(scope="session", autouse=True)
async def dispose_engine(migrated: None):
    yield
    await engine.dispose()  # otherwise pooled connections keep the process alive


@pytest.fixture(autouse=True)
async def clean_db(migrated: None):
    """Empty every table, then restore the seeded settings rows from the same defaults
    migration 0001 uses (TRUNCATE ... CASCADE reaches them through updated_by FKs)."""
    yield
    async with engine.begin() as conn:
        tables = (
            await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'core'"
                    " AND tablename <> 'alembic_version'"
                )
            )
        ).scalars()
        await conn.execute(text(f"TRUNCATE {', '.join(f'core.{t}' for t in tables)} CASCADE"))
        await conn.execute(text("INSERT INTO core.settings (id) VALUES (1)"))
        await conn.execute(insert(Module), [{"key": k} for k in MODULE_KEYS])
        await conn.execute(
            insert(ApprovalChain),
            [
                {"item_type": item, "steps": [{"kind": k} for k in steps]}
                for item, steps in DEFAULT_CHAINS.items()
            ],
        )


@pytest.fixture
async def session():
    async with SessionLocal() as s:
        yield s


@pytest.fixture
async def world(session) -> World:
    w = await build_world(session)
    await session.commit()
    return w


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def auth(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}
