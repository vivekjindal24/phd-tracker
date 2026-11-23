"""A scholar's grievance (grievances.py): who reads it, each step, appeals and deadlines."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app import grievances
from app.models import Grievance, Notification
from tests.conftest import auth
from tests.world import _role, _user

API = "/api/v1/grievances"
BODY = {
    "category": "supervision",
    "subject": "Meetings keep being cancelled",
    "description": "Five of the last six meetings were cancelled without a new date.",
}


@pytest.fixture
async def panel(session, world):
    """A grievance cell of two (one of them Meera, the scholar's own supervisor) and an
    Ombudsperson."""
    cell = await _user(session, "cell_member")
    ombudsperson = await _user(session, "ombudsperson")
    await _role(session, cell, "grievance_cell")
    await _role(session, world.meera, "grievance_cell")
    await _role(session, ombudsperson, "ombudsperson")
    await session.commit()
    return cell, ombudsperson


async def step(client, user, gid, action, body=None):
    return await client.post(f"{API}/{gid}/{action}", headers=auth(user.id), json=body or {})


async def filed(client, world) -> str:
    res = await client.post(API, headers=auth(world.scholar_a1.id), json=BODY)
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def test_a_grievance_reaches_only_those_it_should(client, session, world, panel):
    cell, ombudsperson = panel
    gid = await filed(client, world)
    for user in (world.scholar_a1, cell, world.vice_chancellor):
        res = await client.get(f"{API}/{gid}", headers=auth(user.id))
        assert res.status_code == 200, user.full_name
    # Not the supervisor, even sitting on the cell; no head, admin or other office; nor the
    # Ombudsperson before an appeal; nor another scholar.
    for user in (
        world.meera,
        world.admin_a1,
        world.dean_a,
        world.research_office,
        world.root_admin,
        world.library,
        ombudsperson,
        world.scholar_a1b,
    ):
        res = await client.get(f"{API}/{gid}", headers=auth(user.id))
        assert res.status_code == 403, user.full_name
        listed = await client.get(API, headers=auth(user.id))
        assert listed.status_code == 403 or listed.json() == [], user.full_name
    told = list(
        await session.scalars(select(Notification).where(Notification.link == f"/grievances/{gid}"))
    )
    assert [n.user_id for n in told] == [cell.id]  # the cell, less the scholar's supervisor
    assert told[0].body == "Open it in Anveshan to read it."  # never the grievance's words


async def test_decided_then_appealed_to_the_ombudsperson(client, world, panel):
    cell, ombudsperson = panel
    gid = await filed(client, world)
    view = (await client.get(f"{API}/{gid}", headers=auth(world.scholar_a1.id))).json()
    assert view["due_on"] == str(grievances.working_days_after(date.today(), 15))
    assert (await step(client, world.scholar_a1, gid, "decide", {"text": "x"})).status_code == 409
    res = await step(client, cell, gid, "decide", {"text": "Meetings fixed monthly from now."})
    assert res.status_code == 200 and res.json()["status"] == "decided"
    assert res.json()["decided_by"] == cell.full_name
    res = await step(client, world.scholar_a1, gid, "appeal", {"reason": "Monthly is too rare."})
    assert res.status_code == 200 and res.json()["status"] == "appealed"
    assert res.json()["appeals_to"] == "the Ombudsperson"
    seen = await client.get(f"{API}/{gid}", headers=auth(ombudsperson.id))
    assert seen.status_code == 200 and seen.json()["can"]["decide_appeal"] is True
    vc = await step(client, world.vice_chancellor, gid, "appeal-decision", {"text": "x"})
    assert vc.status_code == 409  # appeals go to the Ombudsperson here
    res = await step(client, ombudsperson, gid, "appeal-decision", {"text": "Fortnightly."})
    assert res.status_code == 200 and res.json()["status"] == "appeal_decided"


async def test_the_university_may_send_appeals_to_the_vice_chancellor(client, world, panel):
    cell, ombudsperson = panel
    res = await client.patch(
        "/api/v1/settings",
        headers=auth(world.root_admin.id),
        json={"grievance_appeals_to": "vice_chancellor"},
    )
    assert res.status_code == 200
    gid = await filed(client, world)
    await step(client, cell, gid, "decide", {"text": "Dismissed."})
    await step(client, world.scholar_a1, gid, "appeal", {"reason": "Not heard."})
    assert (await client.get(f"{API}/{gid}", headers=auth(ombudsperson.id))).status_code == 403
    res = await step(client, world.vice_chancellor, gid, "appeal-decision", {"text": "Rehear."})
    assert res.status_code == 200 and res.json()["status"] == "appeal_decided"


async def test_withdrawn_or_accepted(client, world, panel):
    cell, _ = panel
    gid = await filed(client, world)
    res = await step(client, world.scholar_a1, gid, "withdraw")
    assert res.json()["status"] == "withdrawn"
    assert (await step(client, cell, gid, "decide", {"text": "x"})).status_code == 409
    gid = await filed(client, world)
    await step(client, cell, gid, "decide", {"text": "Resolved."})
    res = await step(client, world.scholar_a1, gid, "accept")
    assert res.json()["status"] == "closed" and res.json()["can"]["appeal"] is False


async def test_the_daily_job_reminds_and_closes(session, world, panel):
    cell, _ = panel
    today = date.today()
    due_soon = Grievance(
        scholar_id=world.s_a1.id, category="other", subject="a", description="a",
        status="open", due_on=today + timedelta(days=3),
    )  # fmt: skip
    overdue = Grievance(
        scholar_id=world.s_a1.id, category="other", subject="b", description="b",
        status="open", due_on=today - timedelta(days=1),
    )  # fmt: skip
    unappealed = Grievance(
        scholar_id=world.s_a1.id, category="other", subject="c", description="c",
        status="decided", due_on=today, decision="d",
        decided_at=datetime.now(UTC) - timedelta(days=16),
    )  # fmt: skip
    session.add_all([due_soon, overdue, unappealed])
    await session.commit()
    counts = await grievances.daily(session, today)
    assert counts == {"grievance_reminders": 1, "grievances_overdue": 1, "grievances_closed": 1}
    assert unappealed.status == "closed"
    late = await session.scalars(
        select(Notification.user_id).where(Notification.link == f"/grievances/{overdue.id}")
    )
    assert set(late) == {cell.id, world.vice_chancellor.id}


async def test_evidence_is_attached_while_open(client, world, panel):
    cell, _ = panel
    gid = await filed(client, world)
    url = "/api/v1/files/uploads"
    file = {"table_name": "grievances", "record_id": gid, "file_name": "minutes.pdf"}
    file |= {"content_type": "application/pdf", "size_bytes": 10}
    assert (await client.post(url, headers=auth(world.meera.id), json=file)).status_code == 403
    await step(client, cell, gid, "decide", {"text": "Done."})
    closed = await client.post(url, headers=auth(world.scholar_a1.id), json=file)
    assert closed.status_code == 409
