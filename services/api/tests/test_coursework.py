"""Coursework (PRD M4, UX Flow 9) and its UGC rules: credits and CGPA minimums warn on the
record and refuse a clearance that would break them."""

from datetime import UTC, datetime

import pytest

from tests.conftest import auth
from tests.test_publications import enable
from tests.test_workflow import notified


@pytest.fixture
async def coursework_on(session, world):
    await enable(session, "coursework")


async def course(client, world, code, credits, unit=None, user=None):
    res = await client.post(
        "/api/v1/courses",
        headers=auth((user or world.exam_office).id),
        json={
            "unit_id": str((unit or world.a1).id),
            "code": code,
            "title": f"Course {code}",
            "credits": credits,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def enrol(client, world, course_id, points=None, grade=None):
    res = await client.post(
        "/api/v1/enrolments",
        headers=auth(world.exam_office.id),
        json={
            "scholar_id": str(world.s_a1.id),
            "course_id": course_id,
            "semester": "2024-25 Odd",
            "grade": grade,
            "grade_points": points,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


async def view(client, user, world):
    return await client.get(f"/api/v1/scholars/{world.s_a1.id}/coursework", headers=auth(user.id))


async def clearance(client, world):
    res = await client.post(
        "/api/v1/clearances",
        headers=auth(world.exam_office.id),
        json={"scholar_id": str(world.s_a1.id)},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def act(client, user, cid, action):
    return await client.post(
        f"/api/v1/items/coursework_clearance/{cid}/{action}", headers=auth(user.id), json={}
    )


async def test_catalogue_writers(client, world, coursework_on):
    await course(client, world, "CS701", 4, user=world.admin_a1)
    res = await client.post(
        "/api/v1/courses",
        headers=auth(world.admin_a1.id),
        json={"unit_id": str(world.b1.id), "code": "B701", "title": "x", "credits": 4},
    )
    assert res.status_code == 403
    res = await client.post(
        "/api/v1/courses",
        headers=auth(world.scholar_a1.id),
        json={"unit_id": str(world.a1.id), "code": "S1", "title": "x", "credits": 4},
    )
    assert res.status_code == 403
    dup = await client.post(
        "/api/v1/courses",
        headers=auth(world.exam_office.id),
        json={"unit_id": str(world.a1.id), "code": "CS701", "title": "x", "credits": 4},
    )
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "duplicate_course"
    listed = await client.get("/api/v1/courses", headers=auth(world.scholar_b1.id))
    assert [c["code"] for c in listed.json()] == ["CS701"]


async def test_rules_warn_then_refuse_then_clear(client, session, world, coursework_on):
    a, b, c = [await course(client, world, code, 4) for code in ("C1", "C2", "C3")]
    await enrol(client, world, a, 8, "A")
    await enrol(client, world, b)  # not graded yet
    mine = (await view(client, world.scholar_a1, world)).json()
    assert mine["credits"] == 4 and mine["cgpa"] == 8
    assert mine["problems"] == [
        "1 course still without a grade",
        "4 credits graded; the minimum is 12",
    ]

    cid = await clearance(client, world)
    refused = await act(client, world.exam_office, cid, "submit")
    assert refused.status_code == 422
    assert "minimum is 12" in refused.json()["error"]["message"]

    enrolments = {e["course"]["code"]: e["id"] for e in mine["enrolments"]}
    await client.patch(
        f"/api/v1/enrolments/{enrolments['C2']}",
        headers=auth(world.exam_office.id),
        json={"grade": "B", "grade_points": 6},
    )
    await enrol(client, world, c, 7, "B+")
    ok = await act(client, world.exam_office, cid, "submit")
    assert ok.status_code == 200
    assert ok.json()["content"]["credits"] == 12 and ok.json()["content"]["cgpa"] == 7

    # Grades are frozen while the clearance is in review.
    locked = await client.patch(
        f"/api/v1/enrolments/{enrolments['C2']}",
        headers=auth(world.exam_office.id),
        json={"grade_points": 9},
    )
    assert locked.status_code == 422

    assert (await act(client, world.meera, cid, "approve")).status_code == 200  # department
    assert (await act(client, world.exam_office, cid, "approve")).status_code == 200
    done = await act(client, world.research_office, cid, "approve")
    assert done.json()["state"] == "approved"
    assert done.json()["content"]["cleared_on"] == datetime.now(UTC).date().isoformat()


async def test_low_cgpa_and_stricter_university_minimum(client, world, coursework_on):
    for code, points in (("L1", 5), ("L2", 5), ("L3", 5)):
        await enrol(client, world, await course(client, world, code, 4), points, "C")
    assert (await view(client, world.exam_office, world)).json()["problems"] == [
        "CGPA 5.00 is below the minimum 5.50"
    ]
    await client.patch(
        "/api/v1/settings",
        headers=auth(world.root_admin.id),
        json={"min_coursework_credits": 16, "min_coursework_cgpa": 5},
    )
    assert (await view(client, world.exam_office, world)).json()["problems"] == [
        "12 credits graded; the minimum is 16"
    ]


async def test_only_the_exam_office_grades(client, world, coursework_on):
    cid = await course(client, world, "G1", 4)
    for user in (world.meera, world.admin_a1, world.scholar_a1, world.research_office):
        res = await client.post(
            "/api/v1/enrolments",
            headers=auth(user.id),
            json={"scholar_id": str(world.s_a1.id), "course_id": cid, "semester": "x"},
        )
        assert res.status_code == 403, user.email
    for user in (world.hod_b1, world.scholar_a2, world.library):
        assert (await view(client, user, world)).status_code == 403, user.email
    for user in (world.scholar_a1, world.meera, world.dean_a, world.research_office):
        assert (await view(client, user, world)).status_code == 200, user.email


async def test_dashboard_shows_coursework_status(client, world, coursework_on):
    await enrol(client, world, await course(client, world, "D1", 4), 9, "A+")
    home = (await client.get("/api/v1/dashboard", headers=auth(world.scholar_a1.id))).json()
    assert home["scholar"]["coursework"] == {
        "credits": 4,
        "min_credits": 12,
        "cgpa": 9,
        "cleared_on": None,
    }


async def test_send_back_to_initiator_notifies_the_exam_office_not_the_scholar(
    client, session, world, coursework_on
):
    for code, points in (("N1", 8), ("N2", 7), ("N3", 6)):
        await enrol(client, world, await course(client, world, code, 4), points, "A")
    cid = await clearance(client, world)
    assert (await act(client, world.exam_office, cid, "submit")).status_code == 200
    assert (await act(client, world.meera, cid, "approve")).status_code == 200
    assert (await act(client, world.exam_office, cid, "approve")).status_code == 200
    back = await client.post(
        f"/api/v1/items/coursework_clearance/{cid}/send-back",
        headers=auth(world.research_office.id),
        json={"comment": "Attach the grade sheet reference.", "to_step": None},
    )
    assert back.status_code == 200 and back.json()["state"] == "sent_back"

    # The Exam Office started it and must resubmit; the scholar cannot act on it.
    assert "sent_back" in await notified(session, world.exam_office)
    assert "sent_back" not in await notified(session, world.scholar_a1)
