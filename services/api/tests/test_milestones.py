"""RDC register: scoped reads; writes by research office anywhere, admins in their unit."""

import pytest

from tests.conftest import auth


def decision(scholar, **extra):
    return {
        "scholar_id": str(scholar.id),
        "milestone_type": "proposal_approval",
        "status": "Approved",
        "approval_body": "RDC",
        "resolution_number": "RDC/2026/14",
        "resolution_date": "2026-09-30",
        **extra,
    }


async def _add(client, user, scholar, **extra):
    return await client.post(
        "/api/v1/milestones", json=decision(scholar, **extra), headers=auth(user.id)
    )


async def test_research_office_records_anywhere(client, world):
    for s in (world.s_a1, world.s_b1):
        res = await _add(client, world.research_office, s)
        assert res.status_code == 201, res.text
    assert res.json()["unit"]["name"] == "Dept B1"


async def test_admin_records_only_in_own_unit(client, world):
    assert (await _add(client, world.admin_a1, world.s_a1)).status_code == 201
    assert (await _add(client, world.admin_a1, world.s_b1)).status_code == 403


@pytest.mark.parametrize("who", ["sup_a2", "dean_a", "exam_office", "scholar_a1"])
async def test_readers_cannot_record(client, world, who):
    assert (await _add(client, getattr(world, who), world.s_a1)).status_code == 403


async def test_reads_follow_scholar_scope(client, world):
    await _add(client, world.research_office, world.s_a1)
    await _add(client, world.research_office, world.s_b1)
    own = (await client.get("/api/v1/milestones", headers=auth(world.scholar_a1.id))).json()
    assert [m["scholar"]["name"] for m in own] == ["Scholar A1"]
    exam = (await client.get("/api/v1/milestones", headers=auth(world.exam_office.id))).json()
    assert len(exam) == 2
    lib = await client.get("/api/v1/milestones", headers=auth(world.library.id))
    assert lib.status_code == 403


async def test_filters_by_unit_and_status(client, world):
    await _add(client, world.research_office, world.s_a1)
    await _add(client, world.research_office, world.s_b1, status="Pending")
    by_unit = await client.get(
        f"/api/v1/milestones?unit_id={world.school_a.id}", headers=auth(world.research_office.id)
    )
    assert [m["scholar"]["name"] for m in by_unit.json()] == ["Scholar A1"]
    pending = await client.get(
        "/api/v1/milestones?status=Pending", headers=auth(world.research_office.id)
    )
    assert [m["scholar"]["name"] for m in pending.json()] == ["Scholar B1"]


async def test_update_and_soft_delete(client, world):
    m = (await _add(client, world.admin_a1, world.s_a1, status="Pending")).json()
    upd = await client.patch(
        f"/api/v1/milestones/{m['id']}",
        json={"status": "Approved"},
        headers=auth(world.admin_a1.id),
    )
    assert upd.json()["status"] == "Approved"
    other = await client.patch(
        f"/api/v1/milestones/{m['id']}", json={"status": "Rejected"}, headers=auth(world.hod_b1.id)
    )
    assert other.status_code == 403
    gone = await client.delete(f"/api/v1/milestones/{m['id']}", headers=auth(world.admin_a1.id))
    assert gone.status_code == 204
    rows = (await client.get("/api/v1/milestones", headers=auth(world.admin_a1.id))).json()
    assert rows == []


async def test_invalid_values_are_422(client, world):
    res = await _add(client, world.research_office, world.s_a1, approval_body="Senate")
    assert res.status_code == 422
