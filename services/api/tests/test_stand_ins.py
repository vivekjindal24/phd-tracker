"""Delegation and escalation at the supervisor step (PRD F3): a named stand-in acts in its
dates, the head after 14 days, both on the supervisor's behalf; the daily job reminds."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from tests.conftest import auth
from tests.test_daily_job import cron_on, inbox, run_daily  # noqa: F401  (fixture)
from tests.test_publications import PUB, enable

TODAY = datetime.now(UTC).date()


@pytest.fixture
async def waiting(client, session, world) -> str:
    """A publication of scholar_b1 waiting at the supervisor step (sup_b1)."""
    await enable(session, "publications")
    res = await client.post("/api/v1/publications", headers=auth(world.scholar_b1.id), json=PUB)
    assert res.status_code == 201, res.text
    pid = res.json()["id"]
    assert (await _act(client, world.scholar_b1, pid, "submit")).status_code == 200
    return pid


async def _act(client, user, pid, action, body=None):
    return await client.post(
        f"/api/v1/items/publication/{pid}/{action}", headers=auth(user.id), json=body or {}
    )


async def _name(client, world, stand_in=None, days=10, start=0):
    return await client.put(
        "/api/v1/faculty/me/stand-in",
        headers=auth(world.sup_b1.id),
        json={
            "stand_in_id": str((stand_in or world.co_sup_faculty).id),
            "starts_on": str(TODAY + timedelta(days=start)),
            "ends_on": str(TODAY + timedelta(days=days)),
        },
    )


async def _age(session, pid, days: int) -> None:
    """Pretend the item last moved `days` ago."""
    await session.execute(
        text(
            "UPDATE core.approval_actions SET at = at - make_interval(days => :d) "
            "WHERE item_id = :i"
        ),
        {"d": days, "i": pid},
    )
    await session.commit()


async def _queue(client, user) -> list[str]:
    res = await client.get("/api/v1/queue", headers=auth(user.id))
    return [q["id"] for q in res.json()]


async def test_supervisor_names_a_colleague_from_their_department(client, world):
    listed = await client.get(
        "/api/v1/faculty/me/stand-in/candidates", headers=auth(world.sup_b1.id)
    )
    assert [c["id"] for c in listed.json()] == [str(world.co_sup_faculty.id)]
    assert (await _name(client, world, world.meera_faculty)).status_code == 422  # other dept
    assert (await _name(client, world, world.sup_b1_faculty)).status_code == 422  # themself
    assert (await _name(client, world, days=-1, start=-5)).status_code == 422  # already over
    assert (await _name(client, world, days=400)).status_code == 422  # too long
    saved = await _name(client, world)
    assert saved.status_code == 200, saved.text
    assert saved.json()["mine"]["stand_in"]["id"] == str(world.co_sup_faculty.id)
    theirs = await client.get("/api/v1/faculty/me/stand-in", headers=auth(world.co_sup.id))
    assert [s["supervisor"]["id"] for s in theirs.json()["standing_in_for"]] == [
        str(world.sup_b1_faculty.id)
    ]
    # Scholars and offices have no stand-in to name.
    for user in (world.scholar_b1, world.research_office):
        res = await client.get("/api/v1/faculty/me/stand-in", headers=auth(user.id))
        assert res.status_code == 403, user.email


async def test_stand_in_acts_on_the_supervisors_behalf_only_in_its_dates(client, world, waiting):
    item = f"/api/v1/items/publication/{waiting}"
    assert (await client.get(item, headers=auth(world.co_sup.id))).status_code == 403
    assert (await _act(client, world.co_sup, waiting, "approve")).status_code == 403
    # Named, but starting next week: nothing yet.
    assert (await _name(client, world, start=7, days=20)).status_code == 200
    assert (await client.get(item, headers=auth(world.co_sup.id))).status_code == 403
    assert (await _name(client, world)).status_code == 200
    assert waiting in await _queue(client, world.co_sup)
    done = await _act(client, world.co_sup, waiting, "approve")
    assert done.status_code == 200, done.text
    last = done.json()["history"][-1]
    assert (last["actor"], last["on_behalf_of"]) == ("Co Sup", "Sup B1")
    # The stand-in ends: so does the view of the supervisor's scholars.
    ended = await client.delete("/api/v1/faculty/me/stand-in", headers=auth(world.sup_b1.id))
    assert ended.status_code == 200 and ended.json()["mine"] is None
    assert (await client.get(item, headers=auth(world.co_sup.id))).status_code == 403


async def test_the_supervisor_acting_themself_is_on_nobodys_behalf(client, world, waiting):
    done = await _act(client, world.sup_b1, waiting, "approve")
    assert done.json()["history"][-1]["on_behalf_of"] is None


async def test_head_steps_in_after_fourteen_days(client, session, world, waiting):
    assert waiting not in await _queue(client, world.hod_b1)
    assert (await _act(client, world.hod_b1, waiting, "approve")).status_code == 422
    await _age(session, waiting, 13)
    assert (await _act(client, world.hod_b1, waiting, "approve")).status_code == 422
    await _age(session, waiting, 1)
    assert waiting in await _queue(client, world.hod_b1)
    # Another department's head never, however long it waits.
    assert (await _act(client, world.hod_a2, waiting, "approve")).status_code == 403
    done = await _act(client, world.hod_b1, waiting, "send-back", {"comment": "Add the DOI."})
    assert done.status_code == 200, done.text
    last = done.json()["history"][-1]
    assert (last["action"], last["on_behalf_of"]) == ("send_back", "Sup B1")


async def test_daily_job_reminds_at_seven_days(client, session, world, waiting, cron_on):  # noqa: F811
    assert (await _name(client, world)).status_code == 200
    await _age(session, waiting, 7)
    counts = await run_daily(client)
    assert (counts["approval_reminders"], counts["approval_escalations"]) == (1, 0)
    for user in (world.sup_b1, world.co_sup):  # the supervisor and their stand-in
        titles = [t for c, t in await inbox(session, user) if c == "approval_waiting"]
        assert any(t.startswith("Still waiting: Publication") for t in titles), user.email
    assert not any(t.startswith("Still waiting") for _, t in await inbox(session, world.hod_b1))


async def test_daily_job_tells_the_head_at_fourteen_days(client, session, world, waiting, cron_on):  # noqa: F811
    await _age(session, waiting, 14)
    counts = await run_daily(client)
    assert (counts["approval_reminders"], counts["approval_escalations"]) == (0, 1)
    assert any(t.startswith("Waiting 14 days") for _, t in await inbox(session, world.hod_b1))
    assert not any(t.startswith("Waiting 14 days") for _, t in await inbox(session, world.hod_a2))
