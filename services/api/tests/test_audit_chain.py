"""The tamper-evident audit trail (migration 0068; SECURITY.md §6): every entry is numbered and
sealed in order, the table refuses changes and removals, and the check finds an entry changed
or removed behind Anveshan's back — and the daily job tells the root admins."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.models import AuditLog, Notification
from tests.conftest import auth
from tests.test_daily_job import cron_on, run_daily  # noqa: F401  (fixture)


async def _check(session) -> tuple[int, int | None]:
    row = (await session.execute(text("SELECT entries, broken_at FROM core.audit_check()"))).one()
    return row.entries, row.broken_at


async def _behind_anveshans_back(session, sql: str) -> None:
    """What someone with only database access could do: switch the guard off, change a row."""
    await session.execute(text("ALTER TABLE core.audit_log DISABLE TRIGGER audit_append_only"))
    await session.execute(text(sql))
    await session.execute(text("ALTER TABLE core.audit_log ENABLE TRIGGER audit_append_only"))
    await session.commit()


async def test_entries_are_numbered_and_sealed_in_order(session, world):
    rows = (await session.scalars(select(AuditLog).order_by(AuditLog.seq))).all()
    assert len(rows) >= 5  # building the world audits the rows it creates
    assert [r.seq for r in rows] == list(range(1, len(rows) + 1))
    assert all(len(r.hash) == 64 for r in rows) and len({r.hash for r in rows}) == len(rows)
    assert await _check(session) == (len(rows), None)


@pytest.mark.parametrize(
    "sql", ["UPDATE core.audit_log SET action = 'lookup'", "DELETE FROM core.audit_log"]
)
async def test_the_trail_refuses_changes_and_removals(session, world, sql):
    with pytest.raises(DBAPIError, match="append-only"):
        await session.execute(text(sql))
    await session.rollback()


async def test_a_changed_entry_is_found(session, world):
    await _behind_anveshans_back(session, "UPDATE core.audit_log SET data = '{}' WHERE seq = 2")
    assert (await _check(session))[1] == 2


async def test_a_removed_entry_is_found(session, world):
    await _behind_anveshans_back(session, "DELETE FROM core.audit_log WHERE seq = 4")
    assert await _check(session) == (3, 5)  # the gap after entry 3


async def test_entries_cannot_be_resealed_without_the_key(session, world):
    """Rewriting a seal with a guessed key does not hold: the check uses the server's key."""
    await _behind_anveshans_back(
        session,
        "UPDATE core.audit_log SET hash = encode(public.hmac('x', 'guess', 'sha256'), 'hex')"
        " WHERE seq = 3",
    )
    assert (await _check(session))[1] == 3


async def test_no_key_no_entry(session, world):
    await session.execute(text("SELECT set_config('anveshan.audit_key', '', false)"))
    with pytest.raises(DBAPIError, match="audit key is not set"):
        await session.execute(
            text(
                "INSERT INTO core.audit_log (table_name, record_id, action) "
                "VALUES ('users', 'x', 'insert')"
            )
        )
    await session.rollback()  # and with it the cleared key: it is back from the connection's start


async def test_who_may_ask_whether_it_is_intact(client, world):
    for user in (world.root_admin, world.research_office):
        res = await client.get("/api/v1/audit-log/integrity", headers=auth(user.id))
        assert res.status_code == 200, res.text
        assert res.json()["intact"] is True and len(res.json()["head"]) == 64
    for user in (world.admin_a1, world.scholar_a1, world.vice_chancellor):
        res = await client.get("/api/v1/audit-log/integrity", headers=auth(user.id))
        assert res.status_code == 403


async def test_the_daily_job_alerts_the_root_admins(client, session, world, cron_on):  # noqa: F811
    assert (await run_daily(client))["audit_trail_intact"] is True
    await session.execute(text("DELETE FROM core.job_runs"))
    await _behind_anveshans_back(session, "UPDATE core.audit_log SET record_id = 'x' WHERE seq = 2")

    assert (await run_daily(client))["audit_trail_intact"] is False
    alerts = await session.scalars(
        select(Notification.user_id).where(Notification.title.contains("tampered"))
    )
    assert set(alerts) == {world.root_admin.id}
