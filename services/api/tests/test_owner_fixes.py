"""What the owner's first browser check turned up (2026-11-19): a self-uploaded signature tells
its keepers; an approver may sign even while signing is not required; opening or handling what a
notification points to reads it; outside committee members carry an email."""

import pytest
from sqlalchemy import select, update

from app.models import Module, Notification
from tests.conftest import auth
from tests.test_signatures import put
from tests.test_signing import PUB, act, code_in, outbox, send_code, specimen  # noqa: F401

API = "/api/v1"


@pytest.fixture
async def pub(session, client, world):
    """A publication waiting at Meera's supervisor step; signing NOT required."""
    await session.execute(update(Module).where(Module.key == "publications").values(enabled=True))
    await session.commit()
    scholar = auth(world.scholar_a1.id)
    pub_id = (await client.post(f"{API}/publications", headers=scholar, json=PUB)).json()["id"]
    await client.post(f"{API}/items/publication/{pub_id}/submit", headers=scholar, json={})
    return pub_id


async def unread(session, user_id, link=None):
    stmt = select(Notification).where(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    )
    if link:
        stmt = stmt.where(Notification.link == link)
    return list(await session.scalars(stmt))


async def test_a_self_uploaded_signature_tells_the_department_admins(session, client, world):
    assert (await put(client, world.scholar_a1, world.scholar_a1)).status_code == 204
    told = await session.scalars(
        select(Notification.user_id).where(Notification.link == "/people/signatures")
    )
    assert set(told) == {world.admin_a1.id, world.meera.id}  # A1's admins, nobody else


async def test_signing_is_optional_when_not_required(session, client, world, pub, outbox):  # noqa: F811
    item = f"{API}/items/publication/{pub}"
    view = await client.get(item, headers=auth(world.meera.id))
    assert view.json()["signing"] == "off"  # no confirmed signature yet
    await specimen(session, world.meera, world.research_office)
    assert (await client.get(item, headers=auth(world.meera.id))).json()["signing"] == "optional"

    chose = await act(client, world.meera, pub, sign=True)
    assert chose.json()["error"]["code"] == "signing_code_required"
    assert (await send_code(client, world.meera, pub)).status_code == 204
    signed = await act(client, world.meera, pub, sign=True, code=code_in(outbox[-1]))
    assert signed.status_code == 200, signed.text
    approval = next(h for h in signed.json()["history"] if h["action"] == "approve")
    assert approval["signature"].startswith("data:image/png")


async def test_unsigned_approval_still_works_when_not_required(session, client, world, pub):
    await specimen(session, world.meera, world.research_office)
    res = await act(client, world.meera, pub)
    assert res.status_code == 200, res.text
    assert next(h for h in res.json()["history"] if h["action"] == "approve")["signature"] is None


async def test_opening_or_handling_reads_the_notification(session, client, world, pub):
    link = f"/items/publication/{pub}"
    meera = world.meera.id
    assert await unread(session, meera, link)
    opened = await client.post(
        f"{API}/notifications/opened", headers=auth(world.meera.id), json={"link": link}
    )
    assert opened.status_code == 200 and opened.json()["unread"] == len(
        await unread(session, meera)
    )
    assert not await unread(session, meera, link)
    # Acting from anywhere (here, straight to the API, as the queue does) reads it too.
    await session.execute(
        update(Notification).where(Notification.link == link).values(read_at=None)
    )
    await session.commit()
    await act(client, world.meera, pub)
    session.expire_all()
    assert not await unread(session, meera, link)


async def test_outside_committee_members_carry_an_email(client, world):
    url = f"{API}/scholars/{world.s_a1.id}/committee"
    admin = auth(world.admin_a1.id)
    fid = (
        await client.post(f"{url}/formations", headers=admin, json={"formed_on": "2022-02-15"})
    ).json()["formations"][0]["id"]
    members = f"{API}/committee-formations/{fid}/members"
    no_email = await client.post(
        members, headers=admin, json={"name": "Dr. X", "institution": "IIT"}
    )
    assert no_email.status_code == 422
    with_email = await client.post(
        members,
        headers=admin,
        json={"name": "Dr. X", "institution": "IIT", "email": "x@iit.example"},
    )
    (member,) = with_email.json()["formations"][0]["members"]
    assert member["email"] == "x@iit.example"
    fixed = await client.patch(
        f"{API}/committee-members/{member['id']}", headers=admin, json={"email": "dr.x@iit.example"}
    )
    assert fixed.json()["formations"][0]["members"][0]["email"] == "dr.x@iit.example"
    # The scholar reads the committee, not the outside member's email.
    own = await client.get(url, headers=auth(world.scholar_a1.id))
    assert own.json()["formations"][0]["members"][0]["email"] is None
