"""Test bootstrap: dedicated test DB, real migration DDL, truncated between tests.

DATABASE_URL must point at a scratch database (CI provides phd_tracker_test via a
service container); conftest creates it locally if missing and applies the real
Alembic migration so tests run against production DDL, including the partial-unique
APR index and trigram search indexes.
"""

import os

if "DATABASE_URL" in os.environ:  # CI points this at the scratch test DB
	TEST_DB_URL = os.environ["DATABASE_URL"]
else:
	TEST_DB_URL = f"postgresql+psycopg://{os.getlogin()}@localhost/phd_tracker_test"
	os.environ["DATABASE_URL"] = TEST_DB_URL  # before any app import — the engine binds to this
os.environ.setdefault("JWT_SECRET", "test-secret-0123456789-0123456789-0123")

import uuid  # noqa: E402

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.auth.service import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, ProgressReport, Scholar, Supervisor, User  # noqa: E402


def _bootstrap_db() -> None:
	admin = create_engine(TEST_DB_URL.rsplit("/", 1)[0] + "/postgres", isolation_level="AUTOCOMMIT")
	with admin.connect() as conn:
		db_name = TEST_DB_URL.rsplit("/", 1)[1]
		if not conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")).scalar():
			conn.execute(text(f'CREATE DATABASE "{db_name}"'))
	admin.dispose()
	command.upgrade(Config("alembic.ini"), "head")


_bootstrap_db()

_truncate_engine = create_engine(TEST_DB_URL)
_tables = ", ".join(f'"core"."{t.name}"' for t in Base.metadata.sorted_tables)


@pytest.fixture(autouse=True)
def clean_db():
	with _truncate_engine.connect() as conn:
		conn.execute(text(f"TRUNCATE {_tables} RESTART IDENTITY CASCADE"))
		conn.commit()
	yield


@pytest.fixture
def client() -> TestClient:
	return TestClient(app)


class Db:
	"""Direct-DB arrangement (fast — no HTTP round trips for setup)."""

	def __init__(self) -> None:
		self._session = Session(_truncate_engine)

	def user(self, email: str, role: str, name: str | None = None) -> uuid.UUID:
		u = User(email=email, password_hash=hash_password("Passw0rd!"), full_name=name or email, role=role)
		self._session.add(u)
		self._session.flush()
		return u.id

	def supervisor(self, email: str, name: str, department: str = "CS",
			designation: str = "Professor", user_id=None) -> uuid.UUID:
		s = Supervisor(user_id=user_id, full_name=name, email=email, department=department,
			designation=designation, max_scholars=8)
		self._session.add(s)
		self._session.flush()
		return s.id

	def scholar(self, roll: str, name: str, supervisor_id=None, user_id=None,
			department: str = "CS") -> uuid.UUID:
		s = Scholar(user_id=user_id, scholar_name=name, roll_number=roll, scholar_email=None,
			department=department, admission_date="2024-07-01", stage="Registered",
			supervisor_id=supervisor_id)
		self._session.add(s)
		self._session.flush()
		return s.id

	def report(self, scholar_id, year: int = 2026, period: str = "January-June",
			state: str = "draft", summary: str = "Work summary") -> uuid.UUID:
		r = ProgressReport(scholar_id=scholar_id, report_year=year, period=period,
			summary=summary, state=state)
		self._session.add(r)
		self._session.flush()
		return r.id

	def commit(self) -> None:
		self._session.commit()

	def close(self) -> None:
		self._session.close()


@pytest.fixture
def db():
	d = Db()
	yield d
	d.close()


def login(client: TestClient, email: str, password: str = "Passw0rd!") -> dict:
	resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
	assert resp.status_code == 200, resp.text
	return resp.json()


def auth_headers(token: str) -> dict:
	return {"Authorization": f"Bearer {token}"}


class Trio:
	"""The standard cast: admin, supervisor Meera (user-linked), scholars A and B (user-linked)."""

	def __init__(self, db: Db) -> None:
		db.user("admin@x.edu", "admin", "Admin")
		sup_user = db.user("meera@x.edu", "supervisor", "Dr. Meera Krishnan")
		self.supervisor_id = db.supervisor("meera@x.edu", "Dr. Meera Krishnan", user_id=sup_user)
		s1_user = db.user("a@x.edu", "scholar", "Asha")
		s2_user = db.user("b@x.edu", "scholar", "Bhavna")
		self.scholar_a = db.scholar("PHD-1", "Asha", supervisor_id=self.supervisor_id, user_id=s1_user)
		self.scholar_b = db.scholar("PHD-2", "Bhavna", supervisor_id=self.supervisor_id, user_id=s2_user)
		db.commit()

	# login convenience
	admin = ("admin@x.edu", "Admin")
	supervisor = ("meera@x.edu", "Dr. Meera Krishnan")
	scholar_a_login = ("a@x.edu", "Asha")
	scholar_b_login = ("b@x.edu", "Bhavna")


@pytest.fixture
def trio(db) -> Trio:
	return Trio(db)