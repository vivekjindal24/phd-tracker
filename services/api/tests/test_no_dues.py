"""No-dues clearance (PRD M3): its own chain on /items, and the thesis gate while the
university setting `require_no_dues` is on — including that scholars see only their own."""

import pytest

from tests.conftest import auth
from tests.test_publications import enable
from tests.test_thesis import act, new_thesis, ready_file

API = "/api/v1"


@pytest.fixture
async def documents_on(session, world):
    await enable(session, "documents")


async def no_dues(client, user, nid, action):
    return await client.post(
        f"{API}/items/no_dues_clearance/{nid}/{action}", headers=auth(user.id), json={}
    )


async def require_no_dues(client, world, on=True):
    res = await client.patch(
        f"{API}/settings", headers=auth(world.root_admin.id), json={"require_no_dues": on}
    )
    assert res.status_code == 200 and res.json()["require_no_dues"] is on


async def cleared(client, world) -> str:
    start = await client.post(f"{API}/no-dues", headers=auth(world.scholar_a1.id))
    assert start.status_code == 201, start.text
    nid = start.json()["id"]
    assert (await no_dues(client, world.scholar_a1, nid, "submit")).status_code == 200
    # lab (supervisor) → department → library → research office (fees)
    for user in (world.meera, world.admin_a1, world.library, world.research_office):
        res = await no_dues(client, user, nid, "approve")
        assert res.status_code == 200, res.text
    assert res.json()["state"] == "approved"
    return nid


async def test_chain_runs_through_every_office(client, world, documents_on):
    mine = (await client.get(f"{API}/no-dues/mine", headers=auth(world.scholar_a1.id))).json()
    assert mine == {"required": False, "item": None}
    nid = await cleared(client, world)
    mine = (await client.get(f"{API}/no-dues/mine", headers=auth(world.scholar_a1.id))).json()
    assert mine["item"]["id"] == nid and mine["item"]["state"] == "approved"


async def test_only_the_current_office_approves(client, world, documents_on):
    nid = (await client.post(f"{API}/no-dues", headers=auth(world.scholar_a1.id))).json()["id"]
    await no_dues(client, world.scholar_a1, nid, "submit")
    early = await no_dues(client, world.library, nid, "approve")  # supervisor's step first
    assert early.json()["error"]["code"] == "workflow_violation"


async def test_scholars_see_only_their_own(client, world, documents_on):
    nid = (await client.post(f"{API}/no-dues", headers=auth(world.scholar_a1.id))).json()["id"]
    other = await client.get(
        f"{API}/items/no_dues_clearance/{nid}", headers=auth(world.scholar_a2.id)
    )
    assert other.status_code == 403
    mine = (await client.get(f"{API}/no-dues/mine", headers=auth(world.scholar_a2.id))).json()
    assert mine["item"] is None
    staff = await client.post(f"{API}/no-dues", headers=auth(world.meera.id))
    assert staff.status_code == 403


async def test_thesis_waits_for_no_dues_only_when_required(client, session, world, documents_on):
    tid = await new_thesis(client, world)
    await ready_file(session, world.scholar_a1, "thesis_submissions", tid)
    await require_no_dues(client, world)
    blocked = await act(client, world.scholar_a1, tid, "submit")
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "no_dues_pending"
    await cleared(client, world)
    assert (await act(client, world.scholar_a1, tid, "submit")).status_code == 200


async def test_thesis_is_not_gated_when_the_setting_is_off(client, session, world, documents_on):
    tid = await new_thesis(client, world)
    await ready_file(session, world.scholar_a1, "thesis_submissions", tid)
    assert (await act(client, world.scholar_a1, tid, "submit")).status_code == 200
