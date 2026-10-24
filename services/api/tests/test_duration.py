"""UGC duration rules, exits and the leadership view (PRD Phase 4)."""

from datetime import date

from app import duration
from app.models import Milestone, Scholar, TimeAdjustment
from tests.conftest import auth

LIMITS = duration.Limits(
    max_years=6, max_extension_days=730, max_relaxation_days=730, max_maternity_leave_days=240
)
TODAY = date(2026, 10, 24)


def scholar(admitted: date | None, stage: str = "Pre-Synopsis", left: date | None = None):
    return Scholar(admission_date=admitted, stage=stage, left_on=left)


def adj(kind: str, start: date, end: date) -> TimeAdjustment:
    return TimeAdjustment(kind=kind, start_date=start, end_date=end)


def test_limit_is_admission_plus_six_years_plus_extensions():
    s = scholar(date(2020, 7, 1))
    plain = duration.assess(s, [], LIMITS, TODAY)
    assert plain["limit_date"] == date(2026, 7, 1) and plain["status"] == "over"
    assert plain["warnings"] == ["Past the maximum duration since 01 Jul 2026"]
    extended = duration.assess(
        s, [adj("extension", date(2026, 7, 1), date(2027, 6, 30))], LIMITS, TODAY
    )
    assert extended["limit_date"] == date(2027, 7, 1)
    assert extended["status"] == "ok" and extended["warnings"] == []
    near = duration.assess(scholar(date(2021, 1, 1)), [], LIMITS, TODAY)
    assert near["status"] == "near" and near["days_left"] == 69


def test_leave_does_not_move_the_limit_but_has_its_own():
    s = scholar(date(2023, 1, 1))
    leave = [adj("maternity_leave", date(2024, 1, 1), date(2024, 9, 30))]  # 274 days
    a = duration.assess(s, leave, LIMITS, TODAY)
    assert a["limit_date"] == date(2029, 1, 1) and a["leave_days"] == 274
    assert a["warnings"] == ["Maternity / child-care leave totals 274 days; the limit is 240"]


def test_rule_stops_mattering_after_submission_or_leaving():
    assert (
        duration.assess(scholar(date(2015, 1, 1), "Thesis Submitted"), [], LIMITS, TODAY)["status"]
        == "done"
    )
    left = duration.assess(scholar(date(2015, 1, 1), left=date(2019, 1, 1)), [], LIMITS, TODAY)
    assert left["status"] == "left" and left["warnings"] == []
    assert duration.assess(scholar(None), [], LIMITS, TODAY)["status"] == "unknown"


async def _admitted(session, s: Scholar, when: date, stage: str | None = None) -> None:
    s.admission_date = when
    if stage:
        s.stage = stage
    session.add(s)
    await session.commit()


async def test_time_records_are_scoped(client, session, world):
    await _admitted(session, world.s_a1, date(2020, 7, 1))
    body = {"kind": "extension", "start_date": "2026-07-01", "end_date": "2027-06-30"}
    url = f"/api/v1/scholars/{world.s_a1.id}/time-adjustments"
    for user in (world.scholar_a1, world.sup_b1, world.hod_b1):
        assert (await client.post(url, headers=auth(user.id), json=body)).status_code == 403
    res = await client.post(url, headers=auth(world.admin_a1.id), json=body)
    assert res.status_code == 200 and res.json()["limit_date"] == "2027-07-01"
    mine = await client.get(
        f"/api/v1/scholars/{world.s_a1.id}/duration", headers=auth(world.scholar_a1.id)
    )
    assert mine.json()["status"] == "ok" and mine.json()["can_manage"] is False
    assert (
        await client.get(
            f"/api/v1/scholars/{world.s_a1.id}/duration", headers=auth(world.hod_b1.id)
        )
    ).status_code == 403
    bad = await client.post(
        url,
        headers=auth(world.research_office.id),
        json=body | {"start_date": "2027-07-01"},
    )
    assert bad.status_code == 422


async def test_leaving_frees_the_supervisors_slot(client, session, world):
    world.meera_faculty.max_scholars = 1  # meera guides scholar_a1
    session.add(world.meera_faculty)
    await session.commit()
    assign = lambda: client.put(  # noqa: E731
        f"/api/v1/scholars/{world.s_a1b.id}/supervisor",
        headers=auth(world.admin_a1.id),
        json={"faculty_id": str(world.meera_faculty.id)},
    )
    assert (await assign()).status_code == 409
    half = await client.patch(
        f"/api/v1/scholars/{world.s_a1.id}",
        headers=auth(world.admin_a1.id),
        json={"left_on": "2026-01-31"},
    )
    assert half.status_code == 422
    left = await client.patch(
        f"/api/v1/scholars/{world.s_a1.id}",
        headers=auth(world.admin_a1.id),
        json={"left_on": "2026-01-31", "left_reason": "withdrawn"},
    )
    assert left.status_code == 200 and left.json()["left_reason"] == "withdrawn"
    assert (await assign()).status_code == 200
    # Coming back would put meera over her cap.
    back = await client.patch(
        f"/api/v1/scholars/{world.s_a1.id}",
        headers=auth(world.admin_a1.id),
        json={"left_on": None, "left_reason": None},
    )
    assert back.status_code == 409 and back.json()["error"]["code"] == "supervisor_cap_exceeded"


async def test_leadership_view(client, session, world):
    await _admitted(session, world.s_a1, date(2015, 7, 1))  # long past the limit, no meetings
    await _admitted(session, world.s_a2, date(2019, 7, 1), stage="Degree Awarded")
    session.add(
        Milestone(
            scholar_id=world.s_a2.id,
            milestone_type="degree_awarded",
            status="Approved",
            approval_body="RDC",
            resolution_date=date(2024, 1, 1),
        )
    )
    world.s_a1b.left_on, world.s_a1b.left_reason = date(2025, 1, 1), "withdrawn"
    session.add(world.s_a1b)
    await session.commit()

    uni = (await client.get("/api/v1/leadership", headers=auth(world.research_office.id))).json()
    assert uni["unit"]["name"] == "Test University"
    assert uni["total"]["completed"] == 1 and uni["total"]["left"] == 1

    school = (await client.get("/api/v1/leadership", headers=auth(world.dean_a.id))).json()
    assert school["unit"]["name"] == "School A"
    rows = {r["unit"]["name"]: r for r in school["by_unit"]}
    assert rows["Dept A1"]["current"] == 1 and rows["Dept A1"]["withdrawn"] == 1
    assert rows["Dept A1"]["dropout_rate"] == 0.5
    assert rows["Dept A2"]["median_years_to_complete"] == 4.5
    risk = {r["scholar"]["name"]: r["reasons"] for r in school["at_risk"]}
    assert "Past the maximum duration since 01 Jul 2021" in risk["Scholar A1"]
    assert "No supervision meeting logged yet" in risk["Scholar A1"]
    assert "Scholar A1B" not in risk  # left: not at risk, counted as a drop-out

    denied = await client.get(
        "/api/v1/leadership", headers=auth(world.hod_b1.id), params={"unit_id": str(world.a1.id)}
    )
    assert denied.status_code == 403
    for user in (world.scholar_a1, world.sup_a2, world.library):
        assert (await client.get("/api/v1/leadership", headers=auth(user.id))).status_code == 403
