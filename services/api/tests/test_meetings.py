"""Meetings: parties see everything; heads/admins/office see minutes only when the main
supervisor shared them (PRD F7, SECURITY.md §3, TESTING.md §1.2)."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select, update

from app.models import Notification, Scholar, Settings
from tests.conftest import auth

TODAY = date.today().isoformat()


def body(scholar, **extra):
    return {
        "scholar_id": str(scholar.id),
        "meeting_date": TODAY,
        "agenda": "Chapter 3 draft",
        "minutes": "Discussed the literature gap.",
        "action_items": "Rewrite section 3.2",
        **extra,
    }


async def _create(client, user, scholar, **extra):
    res = await client.post("/api/v1/meetings", json=body(scholar, **extra), headers=auth(user.id))
    assert res.status_code == 201, res.text
    return res.json()


async def _view(client, user, meeting_id):
    return await client.get(f"/api/v1/meetings/{meeting_id}", headers=auth(user.id))


async def test_supervisor_logs_meeting_scholar_sees_all_and_is_told(client, world, session):
    m = await _create(client, world.meera, world.s_a1)
    assert m["supervisor"]["name"] == "Meera" and m["can_share"] is True
    seen = (await _view(client, world.scholar_a1, m["id"])).json()
    assert seen["minutes"] == "Discussed the literature gap." and seen["redacted"] is False
    told = await session.scalar(
        select(Notification.title).where(Notification.user_id == world.scholar_a1.id)
    )
    assert told.startswith("Meeting on")


async def test_heads_and_office_see_only_that_it_happened(client, world):
    m = await _create(client, world.meera, world.s_a1)
    for viewer in (world.dean_a, world.admin_a1, world.research_office):
        res = (await _view(client, viewer, m["id"])).json()
        assert res["redacted"] is True
        assert res["agenda"] is res["minutes"] is res["action_items"] is None
        assert res["meeting_date"] == TODAY  # ...but they know it happened
    # Out of scope entirely: 403, not a redacted copy.
    assert (await _view(client, world.hod_b1, m["id"])).status_code == 403
    assert (await _view(client, world.scholar_a2, m["id"])).status_code == 403


async def test_sharing_opens_minutes_to_ticked_groups_only(client, world):
    m = await _create(client, world.meera, world.s_a1, shared_with=["unit_heads"])
    assert (await _view(client, world.dean_a, m["id"])).json()["redacted"] is False
    assert (await _view(client, world.admin_a1, m["id"])).json()["redacted"] is True
    assert (await _view(client, world.research_office, m["id"])).json()["redacted"] is True
    await client.patch(
        f"/api/v1/meetings/{m['id']}",
        json={"shared_with": ["research_office"]},
        headers=auth(world.meera.id),
    )
    assert (await _view(client, world.research_office, m["id"])).json()["redacted"] is False
    assert (await _view(client, world.dean_a, m["id"])).json()["redacted"] is True  # unticked


async def test_list_is_redacted_the_same_way(client, world):
    await _create(client, world.meera, world.s_a1)
    rows = (await client.get("/api/v1/meetings", headers=auth(world.dean_a.id))).json()
    assert len(rows) == 1 and rows[0]["minutes"] is None


async def test_scholar_logs_meeting_but_cannot_share(client, world):
    m = await _create(client, world.scholar_a1, world.s_a1)
    assert m["supervisor"]["name"] == "Meera" and m["can_share"] is False
    res = await client.post(
        "/api/v1/meetings",
        json=body(world.s_a1, shared_with=["admins"]),
        headers=auth(world.scholar_a1.id),
    )
    assert res.json()["error"]["code"] == "only_supervisor_shares"


async def test_non_parties_cannot_log_or_edit(client, world):
    for outsider in (world.dean_a, world.admin_a1):
        res = await client.post(
            "/api/v1/meetings", json=body(world.s_a1), headers=auth(outsider.id)
        )
        assert res.status_code == 403
    m = await _create(client, world.meera, world.s_a1)
    edit = await client.patch(
        f"/api/v1/meetings/{m['id']}", json={"agenda": "x"}, headers=auth(world.dean_a.id)
    )
    assert edit.status_code == 403


@pytest.mark.parametrize("office", ["exam_office", "library"])
async def test_offices_without_meeting_rights_get_403(client, world, office):
    res = await client.get("/api/v1/meetings", headers=auth(getattr(world, office).id))
    assert res.status_code == 403


async def test_co_supervisor_follows_the_setting(client, world, session):
    off = await client.post(
        "/api/v1/meetings", json=body(world.s_a1), headers=auth(world.co_sup.id)
    )
    assert off.status_code == 403
    await session.execute(update(Settings).values(co_supervision="view"))
    await session.commit()
    m = await _create(client, world.co_sup, world.s_a1)
    assert m["supervisor"]["name"] == "Co Sup"  # they met the scholar themselves
    assert m["can_share"] is False  # only the main supervisor shares
    share = await client.patch(
        f"/api/v1/meetings/{m['id']}",
        json={"shared_with": ["admins"]},
        headers=auth(world.co_sup.id),
    )
    assert share.json()["error"]["code"] == "only_supervisor_shares"


async def test_meeting_needs_a_supervisor(client, world, session):
    await session.execute(
        update(Scholar).where(Scholar.id == world.s_b1.id).values(supervisor_id=None)
    )
    await session.commit()
    res = await client.post(
        "/api/v1/meetings", json=body(world.s_b1), headers=auth(world.scholar_b1.id)
    )
    assert res.json()["error"]["code"] == "no_supervisor"


async def test_date_rules(client, world):
    future = (date.today() + timedelta(days=5)).isoformat()
    res = await client.post(
        "/api/v1/meetings", json=body(world.s_a1, meeting_date=future), headers=auth(world.meera.id)
    )
    assert res.json()["error"]["code"] == "meeting_in_future"
    backdated = (date.today() - timedelta(days=40)).isoformat()
    ok = await client.post(
        "/api/v1/meetings",
        json=body(world.s_a1, meeting_date=backdated),
        headers=auth(world.meera.id),
    )
    assert ok.status_code == 201  # backdating is real life; created_at shows when it was logged
    bad_next = await client.post(
        "/api/v1/meetings",
        json=body(world.s_a1, next_meeting_date=backdated),
        headers=auth(world.meera.id),
    )
    assert bad_next.json()["error"]["code"] == "next_before_meeting"
