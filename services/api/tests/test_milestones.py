"""RDC register: scoped reads; writes by research office anywhere, admins in their unit."""

from datetime import date

import pytest

from app.enums import MILESTONE_TYPES
from app.models import CommitteeFormation, CommitteeMember, ProgressReport
from tests.conftest import approved_stages, auth


def decision(scholar, **extra):
    return {
        "scholar_id": str(scholar.id),
        "milestone_type": "coursework",
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


async def test_a_stage_needs_the_stage_before_it(client, world):
    office = world.research_office
    early = await _add(client, office, world.s_a1, milestone_type="viva")
    assert (early.status_code, early.json()["error"]["code"]) == (422, "stage_out_of_order")
    assert "Thesis submission" in early.json()["error"]["message"]
    # Recording that it is before the committee is always allowed; approving it is not.
    pending = await _add(client, office, world.s_a1, milestone_type="viva", status="Pending")
    assert pending.status_code == 201
    url = f"/api/v1/milestones/{pending.json()['id']}"
    jump = await client.patch(url, json={"status": "Approved"}, headers=auth(office.id))
    assert jump.json()["error"]["code"] == "stage_out_of_order"
    notes = await client.patch(url, json={"notes": "Adjourned"}, headers=auth(office.id))
    assert notes.status_code == 200
    for stage in MILESTONE_TYPES[:5]:  # coursework … thesis submission, in order
        res = await _add(client, office, world.s_a1, milestone_type=stage)
        assert res.status_code == 201, (stage, res.text)
    assert (
        await client.patch(url, json={"status": "Approved"}, headers=auth(office.id))
    ).status_code == 200


async def test_degree_is_awarded_only_on_a_complete_record(client, world, session):
    scholar = world.s_b1  # no committee, no approved report
    await approved_stages(session, scholar.id, *MILESTONE_TYPES[:6])
    award = {"milestone_type": "degree_awarded"}
    admin = await _add(client, world.root_admin, scholar, **award)
    assert admin.status_code == 403  # admins record the stages; the award is the office's
    bare = await _add(client, world.research_office, scholar, **award)
    assert (bare.status_code, bare.json()["error"]["code"]) == (422, "award_not_ready")
    assert "committee" in bare.json()["error"]["message"]
    assert "progress report" in bare.json()["error"]["message"]
    formation = CommitteeFormation(scholar_id=scholar.id, formed_on=date(2026, 1, 5))
    session.add(formation)
    await session.flush()
    session.add(CommitteeMember(formation_id=formation.id, name="Prof. R. Sen", institution="IIT"))
    session.add(
        ProgressReport(
            scholar_id=scholar.id,
            report_year=2026,
            period="January-June",
            summary="Done.",
            state="approved",
        )
    )
    await session.commit()
    assert (await _add(client, world.research_office, scholar, **award)).status_code == 201
