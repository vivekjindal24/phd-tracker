"""Progress seminars: scheduling rights, notifications, visibility, hardcopy (PRD F15)."""

from sqlalchemy import select, update

from app.models import Notification, Settings
from tests.conftest import auth


def seminar_body(world, unit=None, scholars=None, panel=None, **extra):
    return {
        "unit_id": str((unit or world.a1).id),
        "title": "Autumn progress seminar",
        "starts_at": "2026-11-20T10:00:00+05:30",
        "venue": "Seminar hall 2",
        "report_due": "2026-11-13",
        "report_year": 2026,
        "period": "July-December",
        "scholar_ids": [str(s.id) for s in (scholars or [world.s_a1, world.s_a1b])],
        "panel_faculty_ids": [str(f.id) for f in (panel or [world.sup_b1_faculty])],
        **extra,
    }


async def _schedule(client, user, body):
    return await client.post("/api/v1/seminars", json=body, headers=auth(user.id))


async def _told(session) -> set:
    return set(
        await session.scalars(
            select(Notification.user_id).where(Notification.category == "seminar")
        )
    )


async def test_department_schedules_and_everyone_concerned_is_told(client, world, session):
    res = await _schedule(client, world.admin_a1, seminar_body(world))
    assert res.status_code == 201, res.text
    assert {s["scholar"]["name"] for s in res.json()["scholars"]} == {"Scholar A1", "Scholar A1B"}
    told = await _told(session)
    expected = {
        world.scholar_a1.id,
        world.scholar_a1b.id,  # scholars
        world.meera.id,
        world.sup_a2.id,  # their supervisors (Meera also HoD)
        world.sup_b1.id,  # panel
        world.dean_a.id,
    }  # head above
    assert told == expected
    assert world.co_sup.id not in told  # co-supervision is off


async def test_scholars_must_belong_to_the_unit(client, world):
    res = await _schedule(client, world.admin_a1, seminar_body(world, scholars=[world.s_b1]))
    assert res.json()["error"]["code"] == "scholar_outside_unit"


async def test_who_may_schedule(client, world):
    assert (await _schedule(client, world.hod_a2, seminar_body(world))).status_code == 403
    assert (await _schedule(client, world.sup_a2, seminar_body(world))).status_code == 403
    assert (await _schedule(client, world.dean_a, seminar_body(world))).status_code == 201


async def test_visibility(client, world):
    s = (await _schedule(client, world.admin_a1, seminar_body(world))).json()
    url = f"/api/v1/seminars/{s['id']}"
    for viewer in (
        world.scholar_a1,
        world.sup_b1,
        world.sup_a2,
        world.dean_a,
        world.research_office,
    ):
        assert (await client.get(url, headers=auth(viewer.id))).status_code == 200
    for outsider in (world.scholar_a2, world.hod_b1, world.hod_a2, world.library):
        assert (await client.get(url, headers=auth(outsider.id))).status_code == 403
    listed = await client.get("/api/v1/seminars", headers=auth(world.scholar_a2.id))
    assert listed.json() == []


async def test_detail_shows_each_scholars_report_state(client, world):
    s = (await _schedule(client, world.admin_a1, seminar_body(world))).json()
    summary = "Progress this period: survey finished and first baselines run."
    r = await client.post(
        "/api/v1/reports",
        json={"report_year": 2026, "period": "July-December", "summary": summary},
        headers=auth(world.scholar_a1.id),
    )
    await client.post(
        f"/api/v1/items/progress_report/{r.json()['id']}/submit", headers=auth(world.scholar_a1.id)
    )
    detail = (
        await client.get(f"/api/v1/seminars/{s['id']}", headers=auth(world.admin_a1.id))
    ).json()
    states = {x["scholar"]["name"]: x["report_state"] for x in detail["scholars"]}
    assert states == {"Scholar A1": "in_review", "Scholar A1B": None}
    assert detail["can_manage"] is True


async def test_edit_replaces_scholars_and_cancel_freezes(client, world):
    s = (await _schedule(client, world.admin_a1, seminar_body(world))).json()
    url = f"/api/v1/seminars/{s['id']}"
    edited = await client.patch(
        url,
        json={"scholar_ids": [str(world.s_a1.id)], "venue": "Room 101"},
        headers=auth(world.admin_a1.id),
    )
    body = edited.json()
    assert [x["scholar"]["name"] for x in body["scholars"]] == ["Scholar A1"]
    assert body["venue"] == "Room 101"
    gone = await client.get(url, headers=auth(world.scholar_a1b.id))
    assert gone.status_code == 403  # removed scholar no longer sees it
    cancelled = await client.post(f"{url}/cancel", headers=auth(world.admin_a1.id))
    assert cancelled.json()["status"] == "cancelled"
    frozen = await client.patch(url, json={"venue": "x"}, headers=auth(world.admin_a1.id))
    assert frozen.json()["error"]["code"] == "seminar_cancelled"


async def test_hardcopy_follows_university_setting(client, world, session):
    s = (await _schedule(client, world.admin_a1, seminar_body(world))).json()
    url = f"/api/v1/seminars/{s['id']}/hardcopy/{world.s_a1.id}"
    off = await client.put(url, json={"received_on": "2026-11-12"}, headers=auth(world.admin_a1.id))
    assert off.json()["error"]["code"] == "hardcopy_not_required"
    await session.execute(update(Settings).values(require_hardcopy=True))
    await session.commit()
    on = await client.put(url, json={"received_on": "2026-11-12"}, headers=auth(world.admin_a1.id))
    got = {x["scholar"]["name"]: x["hardcopy_received_on"] for x in on.json()["scholars"]}
    assert got["Scholar A1"] == "2026-11-12"
    by_scholar = await client.put(
        url, json={"received_on": None}, headers=auth(world.scholar_a1.id)
    )
    assert by_scholar.status_code == 403


async def test_seminar_settings_are_validated(client, world):
    dup = await client.patch(
        "/api/v1/settings",
        headers=auth(world.root_admin.id),
        json={"seminar_rubric": [{"name": "Progress", "max": 10}, {"name": "progress", "max": 5}]},
    )
    assert dup.status_code == 422
    ok = await client.patch(
        "/api/v1/settings",
        headers=auth(world.root_admin.id),
        json={
            "seminar_rubric": [{"name": "Overall", "max": 100}],
            "seminar_graders": "panel_and_attending",
            "require_hardcopy": True,
        },
    )
    body = ok.json()
    assert body["seminar_rubric"] == [{"name": "Overall", "max": 100}]
    assert (body["seminar_graders"], body["require_hardcopy"]) == ("panel_and_attending", True)
