"""Requests to faculty outside the caller's view (PRD F6): by email, accepted by the person
asked, for one seminar or scholar, never a way to browse the hidden directory."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.models import AuditLog, FacultyRequest, Notification, Scholar, Settings
from tests.conftest import auth

URL = "/api/v1/faculty-requests"


async def seminar_id(client, world) -> str:
    res = await client.post(
        "/api/v1/seminars",
        headers=auth(world.hod_a2.id),
        json={
            "unit_id": str(world.a2.id),
            "title": "Review",
            "starts_at": "2030-01-10T10:00:00+05:30",
            "report_due": "2030-01-01",
            "report_year": 2029,
            "period": "July-December",
            "scholar_ids": [str(world.s_a2.id)],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def ask(client, user, *, seminar=None, scholar=None, email="sup_b1@x.edu"):
    body = {"email": email, "kind": "seminar_panel" if seminar else "co_supervisor"}
    body |= {"seminar_id": seminar} if seminar else {"scholar_id": str(scholar)}
    return await client.post(URL, json=body, headers=auth(user.id))


async def answer(client, user, request_id, action):
    return await client.post(f"{URL}/{request_id}/{action}", headers=auth(user.id))


async def co_supervision_on(session) -> None:
    await session.execute(update(Settings).values(co_supervision="view"))
    await session.commit()


async def test_accepted_request_adds_the_panel_member_and_nothing_else(client, session, world):
    sid = await seminar_id(client, world)
    res = await ask(client, world.hod_a2, seminar=sid)
    assert res.status_code == 201, res.text
    rid = res.json()["id"]
    seminar = f"/api/v1/seminars/{sid}"
    assert (await client.get(seminar, headers=auth(world.sup_b1.id))).status_code == 403
    told = await session.scalars(
        select(Notification.link).where(Notification.user_id == world.sup_b1.id)
    )
    assert "/requests" in set(told)

    mine = (await client.get(URL, headers=auth(world.sup_b1.id))).json()
    assert [r["id"] for r in mine["incoming"]] == [rid]
    assert "Review" in mine["incoming"][0]["target"]

    assert (await answer(client, world.sup_b1, rid, "accept")).status_code == 200
    assert (await client.get(seminar, headers=auth(world.sup_b1.id))).status_code == 200
    detail = (await client.get(seminar, headers=auth(world.hod_a2.id))).json()
    assert [p["name"] for p in detail["panel"]] == ["Sup B1"]
    names = {f["full_name"] for f in (await client.get(
        "/api/v1/faculty", headers=auth(world.hod_a2.id)
    )).json()}
    assert names == {"Sup A2"}
    sent = (await client.get(URL, headers=auth(world.hod_a2.id))).json()["sent"]
    assert sent[0]["status"] == "accepted" and sent[0]["faculty_name"] == "Sup B1"
    actions = await session.scalars(
        select(AuditLog.action).where(AuditLog.table_name == "faculty_requests")
    )
    assert list(actions).count("insert") == 1


async def test_unknown_email_looks_exactly_like_a_known_one(client, session, world):
    sid = await seminar_id(client, world)
    known = await ask(client, world.hod_a2, seminar=sid)
    unknown = await ask(client, world.hod_a2, seminar=sid, email="nobody@x.edu")
    assert unknown.status_code == known.status_code == 201
    hidden = {"id", "email", "expires_at", "created_at"}
    first = {k: v for k, v in known.json().items() if k not in hidden}
    second = {k: v for k, v in unknown.json().items() if k not in hidden}
    assert first == second and second["faculty_name"] is None
    assert not await session.scalar(
        select(Notification.id).where(
            Notification.user_id != world.sup_b1.id, Notification.link == "/requests"
        )
    )


async def test_only_those_in_charge_may_ask_for_a_seminar(client, world):
    sid = await seminar_id(client, world)
    assert (await ask(client, world.scholar_a2, seminar=sid)).status_code == 403
    assert (await ask(client, world.hod_b1, seminar=sid)).status_code == 403
    assert (await ask(client, world.sup_b1, seminar=sid)).status_code == 403
    assert (await ask(client, world.sup_a2, seminar=sid)).status_code == 201  # scholar's guide


async def test_co_supervisor_request(client, session, world):
    res = await ask(client, world.admin_a1, scholar=world.s_a1b.id)
    assert res.status_code == 422 and res.json()["error"]["code"] == "co_supervision_off"
    await co_supervision_on(session)
    assert (await ask(client, world.sup_b1, scholar=world.s_a1b.id)).status_code == 403
    assert (await ask(client, world.hod_a2, scholar=world.s_a1b.id)).status_code == 403
    taken = await ask(client, world.meera, scholar=world.s_a1.id)
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "co_supervisor_set"

    rid = (await ask(client, world.sup_a2, scholar=world.s_a1b.id)).json()["id"]
    assert (await answer(client, world.sup_b1, rid, "accept")).status_code == 200
    scholar = await session.get(Scholar, world.s_a1b.id)
    await session.refresh(scholar)
    assert scholar.co_supervisor_id == world.sup_b1_faculty.id


async def test_main_supervisor_cannot_accept_as_co_supervisor(client, session, world):
    await co_supervision_on(session)
    res = await ask(client, world.admin_a1, scholar=world.s_a1b.id, email="sup_a2@x.edu")
    res = await answer(client, world.sup_a2, res.json()["id"], "accept")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "co_supervisor_same_as_supervisor"


async def test_only_the_person_asked_may_answer(client, world):
    sid = await seminar_id(client, world)
    rid = (await ask(client, world.hod_a2, seminar=sid)).json()["id"]
    assert (await answer(client, world.co_sup, rid, "accept")).status_code == 403
    assert (await answer(client, world.hod_a2, rid, "accept")).status_code == 403
    assert (await answer(client, world.co_sup, rid, "cancel")).status_code == 403


async def test_expired_request_closes_and_can_be_sent_again(client, session, world):
    sid = await seminar_id(client, world)
    rid = (await ask(client, world.hod_a2, seminar=sid)).json()["id"]
    assert (await ask(client, world.hod_a2, seminar=sid)).status_code == 409
    await session.execute(
        update(FacultyRequest).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await session.commit()
    res = await answer(client, world.sup_b1, rid, "accept")
    assert res.status_code == 422 and res.json()["error"]["code"] == "request_closed"
    assert (await client.get(URL, headers=auth(world.sup_b1.id))).json()["incoming"] == []
    sent = (await client.get(URL, headers=auth(world.hod_a2.id))).json()["sent"]
    assert sent[0]["status"] == "expired"
    assert (await ask(client, world.hod_a2, seminar=sid)).status_code == 201


async def test_declined_and_cancelled_requests_are_closed(client, world):
    sid = await seminar_id(client, world)
    rid = (await ask(client, world.hod_a2, seminar=sid)).json()["id"]
    assert (await answer(client, world.sup_b1, rid, "decline")).status_code == 200
    assert (await answer(client, world.sup_b1, rid, "accept")).status_code == 422
    rid = (await ask(client, world.hod_a2, seminar=sid)).json()["id"]
    assert (await answer(client, world.hod_a2, rid, "cancel")).status_code == 200
    assert (await answer(client, world.sup_b1, rid, "accept")).status_code == 422


async def test_cancelled_seminar_takes_no_requests(client, world):
    sid = await seminar_id(client, world)
    rid = (await ask(client, world.hod_a2, seminar=sid)).json()["id"]
    await client.post(f"/api/v1/seminars/{sid}/cancel", headers=auth(world.hod_a2.id))
    res = await answer(client, world.sup_b1, rid, "accept")
    assert res.status_code == 422 and res.json()["error"]["code"] == "seminar_not_scheduled"
    res = await ask(client, world.hod_a2, seminar=sid, email="co_sup@x.edu")
    assert res.status_code == 422 and res.json()["error"]["code"] == "seminar_not_scheduled"


async def test_attending_faculty_becomes_a_panel_member(client, session, world):
    await session.execute(update(Settings).values(seminar_graders="panel_and_attending"))
    await session.commit()
    sid = await seminar_id(client, world)
    attend = await client.post(
        f"/api/v1/seminars/{sid}/attend", headers=auth(world.sup_b1.id)
    )
    assert attend.status_code == 204, attend.text
    rid = (await ask(client, world.hod_a2, seminar=sid)).json()["id"]
    assert (await answer(client, world.sup_b1, rid, "accept")).status_code == 200
    detail = await client.get(f"/api/v1/seminars/{sid}", headers=auth(world.hod_a2.id))
    assert [(p["name"], p["kind"]) for p in detail.json()["panel"]] == [("Sup B1", "panel")]


async def test_opened_scholar_profile_is_flagged_directory_only(client, session, world):
    from app.models import OrgUnit

    url = f"/api/v1/scholars/{world.s_b1.id}"
    await session.execute(
        update(OrgUnit).where(OrgUnit.id == world.a2.id).values(cross_unit_directory=True)
    )
    await session.commit()
    assert (await client.get(url, headers=auth(world.hod_a2.id))).json()["directory_only"] is True
    assert (await client.get(url, headers=auth(world.hod_b1.id))).json()["directory_only"] is False
