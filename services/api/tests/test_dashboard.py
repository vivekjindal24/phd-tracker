"""Home dashboards (PRD F10): deadlines from seminars, scoped unit numbers, admin gaps."""

from datetime import date, timedelta

import pytest
from sqlalchemy import text, update

from app.dashboard import due_status
from app.models import Scholar
from tests.conftest import auth

TODAY = date.today()


@pytest.mark.parametrize(
    ("due", "state", "expected"),
    [
        (TODAY + timedelta(days=30), None, "upcoming"),
        (TODAY + timedelta(days=14), None, "due_soon"),
        (TODAY - timedelta(days=1), "draft", "overdue"),
        (TODAY - timedelta(days=1), "in_review", "submitted"),
        (TODAY + timedelta(days=3), "approved", "submitted"),
    ],
)
def test_due_status(due, state, expected):
    assert due_status(due, state, TODAY) == expected


async def _seminar(client, world, report_due, starts_in_days=10):
    starts = (TODAY + timedelta(days=starts_in_days)).isoformat() + "T10:00:00+05:30"
    res = await client.post(
        "/api/v1/seminars",
        headers=auth(world.admin_a1.id),
        json={
            "unit_id": str(world.a1.id),
            "title": "Progress seminar",
            "starts_at": starts,
            "report_due": report_due.isoformat(),
            "report_year": 2026,
            "period": "July-December",
            "scholar_ids": [str(world.s_a1.id), str(world.s_a1b.id)],
            "panel_faculty_ids": [],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


async def _dash(client, user):
    res = await client.get("/api/v1/dashboard", headers=auth(user.id))
    assert res.status_code == 200, res.text
    return res.json()


async def test_scholar_sees_next_seminar_and_deadline(client, world):
    await _seminar(client, world, TODAY + timedelta(days=5))
    d = await _dash(client, world.scholar_a1)
    nxt = d["scholar"]["next_seminar"]
    assert nxt["due_status"] == "due_soon" and nxt["title"] == "Progress seminar"
    assert d["scholar"]["supervisor"] == "Meera"
    assert "units" in d and d["units"] == []


async def test_overdue_reports_reach_supervisor_and_heads_but_not_other_units(client, world):
    await _seminar(client, world, TODAY - timedelta(days=2))
    summary = "Progress this period: survey done, first baselines and a draft chapter."
    r = await client.post(
        "/api/v1/reports",
        headers=auth(world.scholar_a1.id),
        json={"report_year": 2026, "period": "July-December", "summary": summary},
    )
    await client.post(
        f"/api/v1/items/progress_report/{r.json()['id']}/submit", headers=auth(world.scholar_a1.id)
    )
    sup = await _dash(client, world.sup_a2)  # supervises scholar_a1b, who never submitted
    assert [o["scholar"]["name"] for o in sup["supervisor"]["overdue_reports"]] == ["Scholar A1B"]
    dean = await _dash(client, world.dean_a)
    (school,) = dean["units"]
    assert [o["scholar"]["name"] for o in school["overdue_reports"]] == ["Scholar A1B"]
    assert {c["name"]: c["overdue"] for c in school["children"]} == {"Dept A1": 1, "Dept A2": 0}
    other = await _dash(client, world.hod_b1)
    assert other["units"][0]["overdue_reports"] == []
    assert other["units"][0]["total_scholars"] == 1


async def test_head_and_admin_of_one_unit_get_one_section_with_admin_extras(client, world, session):
    await session.execute(
        update(Scholar).where(Scholar.id == world.s_a1b.id).values(supervisor_id=None)
    )
    await session.commit()
    d = await _dash(client, world.meera)
    (unit,) = d["units"]
    assert unit["roles"] == ["admin", "unit_head"] and unit["unit_name"] == "Dept A1"
    assert [s["name"] for s in unit["without_supervisor"]] == ["Scholar A1B"]
    assert unit["units_without_head"] == []  # Meera heads A1
    assert d["supervisor"]["load"] == 1  # she supervises scholar_a1
    assert unit["scholars_by_stage"]["Registered"] == 2


async def test_stuck_items_after_fourteen_days(client, world, session):
    summary = "A summary long enough for validation, covering this period's work."
    r = await client.post(
        "/api/v1/reports",
        headers=auth(world.scholar_a1b.id),
        json={"report_year": 2026, "period": "January-June", "summary": summary},
    )
    await client.post(
        f"/api/v1/items/progress_report/{r.json()['id']}/submit", headers=auth(world.scholar_a1b.id)
    )
    await session.execute(text("UPDATE core.approval_actions SET at = now() - interval '20 days'"))
    await session.commit()
    (unit,) = (await _dash(client, world.admin_a1))["units"]
    assert [(s["scholar"], s["step"], s["days"] >= 20) for s in unit["stuck_items"]] == [
        ("Scholar A1B", "Supervisor", True)
    ]


async def test_queue_summary_for_approvers(client, world):
    summary = "A summary long enough for validation, covering this period's work."
    r = await client.post(
        "/api/v1/reports",
        headers=auth(world.scholar_a1b.id),
        json={"report_year": 2026, "period": "January-June", "summary": summary},
    )
    await client.post(
        f"/api/v1/items/progress_report/{r.json()['id']}/submit", headers=auth(world.scholar_a1b.id)
    )
    d = await _dash(client, world.sup_a2)
    assert d["queue_count"] == 1 and d["queue"][0]["step"] == "Supervisor"
