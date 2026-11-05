"""Who sees whom in the directory (SECURITY.md §2-3): the assigned people only, the unit
for heads and admins, the university only where the root admin opened a department."""

from sqlalchemy import update

from app.models import OrgUnit, Settings
from tests.conftest import auth


async def _faculty_names(client, user) -> set[str]:
    res = await client.get("/api/v1/faculty", headers=auth(user.id))
    assert res.status_code == 200, res.text
    return {f["full_name"] for f in res.json()}


async def _rolls(client, user) -> set[str]:
    res = await client.get("/api/v1/scholars", headers=auth(user.id))
    assert res.status_code == 200, res.text
    return {s["roll_number"] for s in res.json()}


async def _open_directory(session, unit) -> None:
    await session.execute(
        update(OrgUnit).where(OrgUnit.id == unit.id).values(cross_unit_directory=True)
    )
    await session.commit()


async def _co_supervision(session, mode: str) -> None:
    await session.execute(update(Settings).values(co_supervision=mode))
    await session.commit()


async def test_scholar_sees_only_their_supervisor(client, world):
    assert await _faculty_names(client, world.scholar_a2) == {"Sup A2"}


async def test_scholar_sees_co_supervisor_only_when_co_supervision_is_on(client, world, session):
    assert await _faculty_names(client, world.scholar_a1) == {"Meera"}
    await _co_supervision(session, "view")
    assert await _faculty_names(client, world.scholar_a1) == {"Meera", "Co Sup"}


async def test_supervisor_sees_self_only_without_shared_scholars(client, world):
    assert await _faculty_names(client, world.sup_b1) == {"Sup B1"}


async def test_co_supervisor_sees_the_main_supervisor_they_share_a_scholar_with(
    client, world, session
):
    await _co_supervision(session, "view")
    assert await _faculty_names(client, world.co_sup) == {"Co Sup", "Meera"}


async def test_head_sees_own_department_faculty_only(client, world):
    assert await _faculty_names(client, world.hod_b1) == {"Sup B1", "Co Sup"}
    assert await _faculty_names(client, world.hod_a2) == {"Sup A2"}


async def test_dean_sees_the_whole_school_and_no_other(client, world):
    assert await _faculty_names(client, world.dean_a) == {"Meera", "Sup A2"}


async def test_offices_and_root_admin_see_all_faculty(client, world):
    for user in (world.root_admin, world.research_office, world.exam_office, world.library):
        assert len(await _faculty_names(client, user)) == 4


async def test_out_of_scope_faculty_detail_is_403(client, world):
    url = f"/api/v1/faculty/{world.sup_b1_faculty.id}"
    assert (await client.get(url, headers=auth(world.scholar_a1.id))).status_code == 403
    assert (await client.get(url, headers=auth(world.hod_a2.id))).status_code == 403
    assert (await client.get(url, headers=auth(world.hod_b1.id))).status_code == 200


async def test_search_does_not_reveal_out_of_scope_faculty(client, world):
    res = await client.get("/api/v1/search?q=Sup B1", headers=auth(world.scholar_a1.id))
    assert res.json()["faculty"] == []
    res = await client.get("/api/v1/search?q=Sup B1", headers=auth(world.hod_b1.id))
    assert [f["title"] for f in res.json()["faculty"]] == ["Sup B1"]


async def test_opening_a_department_widens_only_its_own_heads_and_admins(client, world, session):
    await _open_directory(session, world.a2)
    assert len(await _faculty_names(client, world.hod_a2)) == 4
    assert len(await _rolls(client, world.hod_a2)) == 4
    assert await _faculty_names(client, world.hod_b1) == {"Sup B1", "Co Sup"}
    assert await _rolls(client, world.hod_b1) == {"PHD-B1-001"}
    assert await _faculty_names(client, world.sup_a2) == {"Sup A2"}


async def test_opening_a_department_never_opens_records(client, world, session):
    await _open_directory(session, world.a2)
    headers = auth(world.hod_a2.id)
    other = world.s_b1.id
    assert (await client.get(f"/api/v1/scholars/{other}", headers=headers)).status_code == 200
    url = f"/api/v1/scholars/{other}/timeline"
    assert (await client.get(url, headers=headers)).status_code == 403
    url = f"/api/v1/meetings?scholar_id={other}"
    assert (await client.get(url, headers=headers)).json() == []
    comment = {"table_name": "scholars", "record_id": str(other), "body": "hello"}
    assert (await client.post("/api/v1/comments", json=comment, headers=headers)).status_code == 403
    res = await client.patch(
        f"/api/v1/scholars/{other}", json={"research_title": "x"}, headers=headers
    )
    assert res.status_code == 403


async def test_only_root_admin_opens_a_department(client, world):
    url = f"/api/v1/org-units/{world.a2.id}"
    body = {"cross_unit_directory": True}
    assert (await client.patch(url, json=body, headers=auth(world.hod_a2.id))).status_code == 403
    res = await client.patch(url, json=body, headers=auth(world.root_admin.id))
    assert res.status_code == 200 and res.json()["cross_unit_directory"] is True
    bad = {"cross_unit_directory": None}
    assert (await client.patch(url, json=bad, headers=auth(world.root_admin.id))).status_code == 422
