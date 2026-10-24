"""The daily job's reminders (PRD F5, ARCHITECTURE.md §10): APR due in 14 days / overdue,
meeting tomorrow. The fellowship reminder is tested with the grants module."""

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.config import settings
from app.models import Meeting, Notification, Seminar, SeminarScholar
from app.routers import cron
from tests.conftest import auth

SECRET = "s" * 40


@pytest.fixture
def cron_on(monkeypatch):
    monkeypatch.setattr(cron, "settings", dataclasses.replace(settings, cron_secret=SECRET))


async def run_daily(client) -> dict:
    res = await client.post("/api/v1/internal/cron/daily", headers={"X-Cron-Secret": SECRET})
    assert res.status_code == 200, res.text
    return res.json()


async def inbox(session, user) -> list[tuple[str, str]]:
    rows = await session.execute(
        select(Notification.category, Notification.title).where(Notification.user_id == user.id)
    )
    return list(rows)


async def seminar(session, world, scholars, due_in_days: int) -> None:
    today = datetime.now(UTC).date()
    s = Seminar(
        unit_id=world.a1.id,
        title="Progress seminar",
        starts_at=datetime.now(UTC) + timedelta(days=due_in_days + 7),
        report_due=today + timedelta(days=due_in_days),
        report_year=today.year,
        period="July-December",
        created_by=world.meera.id,
    )
    session.add(s)
    await session.flush()
    session.add_all(SeminarScholar(seminar_id=s.id, scholar_id=sc.id) for sc in scholars)
    await session.commit()


async def test_apr_due_soon_and_overdue(client, session, world, cron_on):
    await seminar(session, world, [world.s_a1, world.s_b1], due_in_days=14)
    await seminar(session, world, [world.s_a2], due_in_days=-1)
    # s_b1 has already submitted: no reminder for a report that is on its way.
    created = await client.post(
        "/api/v1/reports",
        headers=auth(world.scholar_b1.id),
        json={
            "report_year": datetime.now(UTC).year,
            "period": "July-December",
            "summary": "Two chapters drafted and one paper under review.",
        },
    )
    rid = created.json()["id"]
    submitted = await client.post(
        f"/api/v1/items/progress_report/{rid}/submit", headers=auth(world.scholar_b1.id)
    )
    assert submitted.status_code == 200

    result = await run_daily(client)
    assert result["apr_due_soon"] == 1 and result["apr_overdue"] == 1

    assert [c for c, _ in await inbox(session, world.scholar_a1)] == ["apr_due"]
    assert [c for c, _ in await inbox(session, world.meera)] == []  # due soon: scholar only
    assert "apr_due" not in [c for c, _ in await inbox(session, world.scholar_b1)]
    for user in (world.scholar_a2, world.sup_a2):  # overdue: scholar and supervisor
        assert [c for c, _ in await inbox(session, user)] == ["apr_due"]


async def test_meeting_tomorrow_from_the_latest_logged_meeting(client, session, world, cron_on):
    today = datetime.now(UTC).date()
    tomorrow = today + timedelta(days=1)

    def meeting(scholar, faculty, days_ago, next_date):
        return Meeting(
            scholar_id=scholar.id,
            supervisor_id=faculty.id,
            meeting_date=today - timedelta(days=days_ago),
            agenda="Progress",
            next_meeting_date=next_date,
            created_by=world.meera.id,
        )

    session.add_all(
        [
            meeting(world.s_a1, world.meera_faculty, 14, tomorrow),
            # s_a2's plan for tomorrow was replaced by a newer meeting with no next date.
            meeting(world.s_a2, world.sup_a2_faculty, 20, tomorrow),
            meeting(world.s_a2, world.sup_a2_faculty, 3, None),
        ]
    )
    await session.commit()

    result = await run_daily(client)
    assert result["meeting_reminders"] == 1
    for user in (world.scholar_a1, world.meera):
        assert [c for c, _ in await inbox(session, user)] == ["meeting_tomorrow"]
    for user in (world.scholar_a2, world.sup_a2):
        assert await inbox(session, user) == []
