"""Change of supervisor through an approval chain (supervisor_changes.py)."""

from sqlalchemy import select

from app.models import Notification, Scholar, SupervisorAppointment
from tests.conftest import auth

API = "/api/v1"


async def act(client, user, cid, action):
    return await client.post(
        f"{API}/items/supervisor_change/{cid}/{action}", headers=auth(user.id), json={}
    )


async def propose(client, world, user=None, **over):
    body = {
        "to_faculty_id": str(world.sup_a2_faculty.id),
        "reason": "Dr. Meera moves to the Data Science centre.",
        "scholar_consent": True,
        "order_ref": "DU/R/2026/77",
        "effective_on": "2026-11-01",
    } | over
    return await client.post(
        f"{API}/scholars/{world.s_a1.id}/supervisor-changes",
        headers=auth((user or world.admin_a1).id),
        json=body,
    )


async def test_a_supervisor_changes_only_once_the_chain_approves(client, session, world):
    # Directly, no longer: an existing supervisor is changed by an approved proposal.
    direct = await client.put(
        f"{API}/scholars/{world.s_a1.id}/supervisor",
        headers=auth(world.admin_a1.id),
        json={"faculty_id": str(world.sup_a2_faculty.id)},
    )
    assert direct.status_code == 409
    assert direct.json()["error"]["code"] == "supervisor_change_needs_approval"

    res = await propose(client, world)
    assert res.status_code == 201, res.text
    cid = res.json()["id"]
    assert res.json()["content"]["from"]["name"] == world.meera.full_name
    assert (await propose(client, world)).status_code == 409  # one open change per scholar

    sent = await act(client, world.admin_a1, cid, "submit")
    assert sent.status_code == 200
    assert sent.json()["send_back_targets"][0]["label"] == "Back to the department admin"
    assert (await act(client, world.admin_a1, cid, "approve")).status_code == 200  # Department
    scholar = await session.get(Scholar, world.s_a1.id)
    await session.refresh(scholar)
    assert scholar.supervisor_id == world.meera_faculty.id  # not yet: the office approves last
    res = await act(client, world.research_office, cid, "approve")
    assert res.status_code == 200 and res.json()["state"] == "approved", res.text

    await session.refresh(scholar)
    assert scholar.supervisor_id == world.sup_a2_faculty.id
    rows = list(
        await session.scalars(
            select(SupervisorAppointment)
            .where(SupervisorAppointment.scholar_id == world.s_a1.id)
            .order_by(SupervisorAppointment.created_at)
        )
    )
    old, new = rows[-2], rows[-1]
    assert old.faculty_id == world.meera_faculty.id and str(old.ended_on) == "2026-11-01"
    assert new.faculty_id == world.sup_a2_faculty.id and new.order_ref == "DU/R/2026/77"
    assert str(new.appointed_on) == "2026-11-01" and new.ended_on is None
    told = set(
        await session.scalars(
            select(Notification.title).where(
                Notification.user_id.in_([world.meera.id, world.sup_a2.id, world.scholar_a1.id])
            )
        )
    )
    assert "Your supervisor has changed" in told
    assert any(t.startswith("You are no longer") for t in told)
    assert any(t.endswith("is now your scholar") for t in told)
    # Settled: a new change can be proposed again.
    assert (
        await propose(client, world, to_faculty_id=str(world.meera_faculty.id))
    ).status_code == 201


async def test_who_proposes_and_what_is_refused(client, world):
    assert (await propose(client, world, user=world.scholar_a1)).status_code == 403
    assert (await propose(client, world, user=world.sup_b1)).status_code == 403
    same = await propose(client, world, to_faculty_id=str(world.meera_faculty.id))
    assert same.status_code == 422 and same.json()["error"]["code"] == "same_supervisor"
    blank = await propose(client, world, reason=" ")
    assert blank.status_code == 422


async def test_the_proposal_is_edited_or_withdrawn_while_a_draft(client, world):
    cid = (await propose(client, world)).json()["id"]
    res = await client.patch(
        f"{API}/supervisor-changes/{cid}",
        headers=auth(world.admin_a1.id),
        json={"reason": "Retirement of the supervisor."},
    )
    assert (
        res.status_code == 200
        and res.json()["content"]["reason"] == "Retirement of the supervisor."
    )
    gone = await client.delete(f"{API}/supervisor-changes/{cid}", headers=auth(world.admin_a1.id))
    assert gone.status_code == 204
    assert (await propose(client, world)).status_code == 201  # withdrawn: no longer open
