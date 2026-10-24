"""Admissions (PRD M5, UX Flow 10): scoped to the unit, offices see all; a selected candidate
becomes a scholar with a login."""

import pytest
from sqlalchemy import select

from app.models import Scholar, User
from tests.conftest import auth
from tests.test_publications import enable

CANDIDATE = {
    "candidate_name": "Kavya Menon",
    "email": "kavya@x.edu",
    "entrance_route": "net_jrf",
    "entrance_score": 92.5,
    "interview_date": "2026-07-01",
    "admitted_on": "2026-07-15",
}


@pytest.fixture
async def admissions_on(session, world):
    await enable(session, "admissions")


async def admit(client, world, user=None, unit=None, **over):
    res = await client.post(
        "/api/v1/admissions",
        headers=auth((user or world.admin_a1).id),
        json=CANDIDATE | {"unit_id": str((unit or world.a1).id)} | over,
    )
    return res


async def test_scoped_like_the_unit(client, world, admissions_on):
    assert (await admit(client, world)).status_code == 201
    assert (await admit(client, world, unit=world.b1)).status_code == 403
    assert (
        await admit(client, world, user=world.research_office, unit=world.b1, email="r@x.edu")
    ).status_code == 201
    names = lambda res: sorted(a["unit"]["name"] for a in res.json())  # noqa: E731
    assert names(await client.get("/api/v1/admissions", headers=auth(world.dean_a.id))) == [
        "Dept A1"
    ]
    assert names(await client.get("/api/v1/admissions", headers=auth(world.hod_b1.id))) == [
        "Dept B1"
    ]
    assert (
        len((await client.get("/api/v1/admissions", headers=auth(world.research_office.id))).json())
        == 2
    )
    for user in (world.scholar_a1, world.sup_a2, world.exam_office):
        assert (await client.get("/api/v1/admissions", headers=auth(user.id))).status_code == 403
    # A head reads but does not write.
    row = (await client.get("/api/v1/admissions", headers=auth(world.dean_a.id))).json()[0]
    assert row["can_edit"] is False
    res = await client.patch(
        f"/api/v1/admissions/{row['id']}", headers=auth(world.dean_a.id), json={"phone": "1"}
    )
    assert res.status_code == 403


async def test_convert_selected_candidate(client, session, world, admissions_on):
    aid = (await admit(client, world)).json()["id"]
    body = {"roll_number": "PHD-A1-2026-01", "password": "a-strong-password"}
    early = await client.post(
        f"/api/v1/admissions/{aid}/convert", headers=auth(world.admin_a1.id), json=body
    )
    assert early.status_code == 422 and early.json()["error"]["code"] == "not_selected"
    await client.patch(
        f"/api/v1/admissions/{aid}",
        headers=auth(world.admin_a1.id),
        json={"interview_result": "selected"},
    )
    res = await client.post(
        f"/api/v1/admissions/{aid}/convert", headers=auth(world.admin_a1.id), json=body
    )
    assert res.status_code == 200, res.text
    scholar = await session.get(Scholar, res.json()["scholar_id"])
    user = await session.scalar(select(User).where(User.id == scholar.user_id))
    assert (user.email, user.full_name) == ("kavya@x.edu", "Kavya Menon")
    assert scholar.unit_id == world.a1.id and str(scholar.admission_date) == "2026-07-15"
    again = await client.post(
        f"/api/v1/admissions/{aid}/convert", headers=auth(world.admin_a1.id), json=body
    )
    assert again.json()["error"]["code"] == "already_converted"
    gone = await client.delete(f"/api/v1/admissions/{aid}", headers=auth(world.admin_a1.id))
    assert gone.status_code == 422  # a converted admission stays on record


async def test_research_office_converts_anywhere(client, world, admissions_on):
    res = await admit(
        client, world, user=world.research_office, unit=world.b1, interview_result="selected"
    )
    aid = res.json()["id"]
    out = await client.post(
        f"/api/v1/admissions/{aid}/convert",
        headers=auth(world.research_office.id),
        json={"roll_number": "PHD-B1-2026-01", "password": "a-strong-password"},
    )
    assert out.status_code == 200


async def test_convert_without_email_needs_a_password(client, world, admissions_on):
    aid = (await admit(client, world, interview_result="selected")).json()["id"]
    res = await client.post(
        f"/api/v1/admissions/{aid}/convert",
        headers=auth(world.admin_a1.id),
        json={"roll_number": "PHD-X"},
    )
    assert res.status_code == 422 and res.json()["error"]["code"] == "email_not_configured"
