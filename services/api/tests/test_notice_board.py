"""The notice board (announcements.py): university-wide and department notices."""

from sqlalchemy import select

from app.models import Notification
from tests.conftest import auth

API = "/api/v1/announcements"


async def post(client, user, **body):
    return await client.post(API, headers=auth(user.id), json={"title": "Fee notice"} | body)


async def titles(client, user, past=False):
    res = await client.get(f"{API}?past={str(past).lower()}", headers=auth(user.id))
    assert res.status_code == 200, res.text
    return [n["title"] for n in res.json()]


async def test_a_university_notice_reaches_everyone(client, session, world):
    res = await post(client, world.research_office, body="Semester fees are due by 30 Nov.")
    assert res.status_code == 201, res.text
    assert res.json()["unit"] is None and res.json()["can_manage"]
    for user in (world.scholar_a1, world.scholar_b1, world.sup_b1, world.hod_b1):
        assert await titles(client, user) == ["Fee notice"]
    told = await session.scalars(
        select(Notification.user_id).where(Notification.category == "notice")
    )
    assert {world.scholar_a1.id, world.scholar_b1.id} <= set(told)


async def test_a_department_notice_stays_in_the_department(client, world):
    res = await post(client, world.admin_a1, unit_id=str(world.a1.id), title="A1 seminar week")
    assert res.status_code == 201, res.text
    assert await titles(client, world.scholar_a1) == ["A1 seminar week"]
    assert await titles(client, world.dean_a) == ["A1 seminar week"]  # the head above sees it
    assert await titles(client, world.research_office) == ["A1 seminar week"]
    assert await titles(client, world.scholar_b1) == []
    assert await titles(client, world.hod_b1) == []


async def test_who_may_post_where(client, world):
    assert (await post(client, world.admin_a1)).status_code == 403  # not university-wide
    assert (await post(client, world.admin_a1, unit_id=str(world.b1.id))).status_code == 403
    assert (await post(client, world.scholar_a1, unit_id=str(world.a1.id))).status_code == 403
    assert (await post(client, world.hod_b1, unit_id=str(world.b1.id))).status_code == 403
    where = (await client.get(f"{API}/where", headers=auth(world.admin_a1.id))).json()
    assert where["university"] is False
    assert str(world.a1.id) in {u["id"] for u in where["units"]}
    assert str(world.b1.id) not in {u["id"] for u in where["units"]}


async def test_ended_pinned_edited_and_removed(client, world):
    office = world.research_office
    await post(client, office, title="Old notice", ends_on="2020-01-01")
    nid = (await post(client, office, title="Fee notice")).json()["id"]
    await post(client, office, title="Pinned", pinned=True)
    assert await titles(client, world.scholar_a1) == ["Pinned", "Fee notice"]
    assert await titles(client, world.scholar_a1, past=True) == ["Old notice"]

    res = await client.patch(f"{API}/{nid}", headers=auth(office.id), json={"title": "Fees due"})
    assert res.status_code == 200 and res.json()["title"] == "Fees due"
    gone = await client.delete(f"{API}/{nid}", headers=auth(world.scholar_a1.id))
    assert gone.status_code == 403
    assert (await client.delete(f"{API}/{nid}", headers=auth(office.id))).status_code == 204
    assert await titles(client, world.scholar_a1) == ["Pinned"]


async def test_a_notice_file_is_attached_by_whoever_may_post_it(client, world):
    nid = (await post(client, world.admin_a1, unit_id=str(world.a1.id))).json()["id"]

    def upload(user):
        return client.post(
            "/api/v1/files/uploads",
            headers=auth(user.id),
            json={
                "table_name": "announcements",
                "record_id": nid,
                "file_name": "fee-notice.pdf",
                "content_type": "application/pdf",
                "size_bytes": 100,
            },
        )

    assert (await upload(world.admin_a1)).status_code == 201
    assert (await upload(world.scholar_a1)).status_code == 403  # reads it, cannot attach
    assert (await upload(world.scholar_b1)).status_code == 403  # cannot even read it
