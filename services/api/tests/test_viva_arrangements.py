"""Viva arrangements (PRD M3, Forms X and XI): the Exam Office proposes the date, place and
board; the Vice Chancellor approves; the external examiners are emailed; the viva is then
recorded against the approved arrangement. External examiners stay unnamed to the scholar
and the guide until the viva is recorded."""

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import notify, viva
from app.config import Smtp, settings
from app.models import Notification
from tests.conftest import auth
from tests.test_publications import enable
from tests.test_thesis import add_report, approved_thesis, evaluation

API = "/api/v1"
SOON = (datetime.now(UTC) + timedelta(days=10)).isoformat()
EXAMINER = {
    "role": "external_examiner",
    "name": "Prof. K. Rao",
    "institution": "IISc Bengaluru",
    "email": "rao@iisc.example",
}


@pytest.fixture
async def documents_on(session, world):
    await enable(session, "documents")


async def arrange(client, world, tid, user=None, **over):
    return await client.post(
        f"{API}/theses/{tid}/viva-arrangements",
        headers=auth((user or world.exam_office).id),
        json={"scheduled_at": SOON, "venue": "Senate Hall"} | over,
    )


async def board_add(client, world, aid, body, user=None):
    return await client.post(
        f"{API}/viva-arrangements/{aid}/board",
        headers=auth((user or world.exam_office).id),
        json=body,
    )


async def act(client, user, aid, action):
    return await client.post(
        f"{API}/items/viva_arrangement/{aid}/{action}", headers=auth(user.id), json={}
    )


async def ready_arrangement(client, session, world) -> tuple[str, str]:
    """An approved thesis with released reports and a full board, still a draft."""
    tid = await approved_thesis(client, session, world)
    await add_report(client, world, tid)
    res = await arrange(client, world, tid)
    assert res.status_code == 201, res.text
    aid = res.json()["id"]
    chair = {"role": "chairperson", "faculty_id": str(world.sup_a2_faculty.id)}
    for body in (chair, EXAMINER):
        assert (await board_add(client, world, aid, body)).status_code == 200
    return tid, aid


async def test_arranged_approved_invited_then_recorded(
    client, session, world, documents_on, monkeypatch
):
    tid, aid = await ready_arrangement(client, session, world)
    assert (await act(client, world.exam_office, aid, "submit")).json()["state"] == "in_review"
    early = await client.post(
        f"{API}/theses/{tid}/vivas",
        headers=auth(world.exam_office.id),
        json={"held_on": "2026-10-10", "outcome": "pass"},
    )
    assert early.json()["error"]["code"] == "viva_not_approved"  # not yet approved
    approved = await act(client, world.vice_chancellor, aid, "approve")
    assert approved.json()["state"] == "approved", approved.text
    # The supervisor and the faculty on the board are told when and where.
    told = await session.scalars(
        select(Notification.user_id).where(Notification.title == "A viva you sit on is approved")
    )
    assert set(told) == {world.meera.id, world.sup_a2.id}

    sent: list[tuple[str, str]] = []

    async def fake_send(to, subject, body):
        sent.append((to, body))

    smtp = Smtp(host="smtp.test", port=587, user="u", password="p", mail_from="noreply@x.edu")
    monkeypatch.setattr(notify, "settings", dataclasses.replace(settings, smtp=smtp))
    monkeypatch.setattr(viva, "send_email", fake_send)
    invited = await client.post(
        f"{API}/viva-arrangements/{aid}/invite", headers=auth(world.exam_office.id)
    )
    assert invited.status_code == 200 and invited.json()["sent"] == 1, invited.text
    assert sent[0][0] == "rao@iisc.example" and "Senate Hall" in sent[0][1]

    recorded = await client.post(
        f"{API}/theses/{tid}/vivas",
        headers=auth(world.exam_office.id),
        json={"held_on": "2026-10-10", "outcome": "pass"},
    )
    assert recorded.status_code == 200, recorded.text
    view = (await evaluation(client, world.exam_office, tid)).json()
    assert view["arrangements"][0]["held"] and not view["can_arrange_viva"]
    # Recorded: the examiner may be named to the scholar now; no more invitations.
    board = await client.get(
        f"{API}/viva-arrangements/{aid}/board", headers=auth(world.scholar_a1.id)
    )
    names = [m["name"] for m in board.json()["members"]]
    assert "Prof. K. Rao" in names and not board.json()["can_invite"]


async def test_examiner_names_hidden_from_scholar_and_guide(client, session, world, documents_on):
    _, aid = await ready_arrangement(client, session, world)
    url = f"{API}/viva-arrangements/{aid}/board"
    for user in (world.scholar_a1, world.meera):
        board = (await client.get(url, headers=auth(user.id))).json()
        examiner = next(m for m in board["members"] if m["role"] == "external_examiner")
        assert board["names_hidden"] and examiner["name"] is None and examiner["email"] is None
        assert board["supervisor"] == "Meera" and not board["can_edit"]
    office = (await client.get(url, headers=auth(world.exam_office.id))).json()
    assert [m["name"] for m in office["members"]] == ["Sup A2", "Prof. K. Rao"]
    assert office["can_edit"]


async def test_submit_needs_a_future_date_a_place_and_a_board(client, session, world, documents_on):
    tid = await approved_thesis(client, session, world)
    await add_report(client, world, tid)
    aid = (await arrange(client, world, tid, venue="")).json()["id"]
    no_place = await act(client, world.exam_office, aid, "submit")
    assert "venue" in no_place.json()["error"]["message"]
    await client.patch(
        f"{API}/viva-arrangements/{aid}",
        headers=auth(world.exam_office.id),
        json={"online_link": "https://meet.example/viva"},
    )
    no_board = await act(client, world.exam_office, aid, "submit")
    assert "chairperson" in no_board.json()["error"]["message"]
    await board_add(
        client, world, aid, {"role": "chairperson", "faculty_id": str(world.sup_a2_faculty.id)}
    )
    await board_add(client, world, aid, EXAMINER)
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    await client.patch(
        f"{API}/viva-arrangements/{aid}",
        headers=auth(world.exam_office.id),
        json={"scheduled_at": past},
    )
    assert (
        "still to come"
        in (await act(client, world.exam_office, aid, "submit")).json()["error"]["message"]
    )


async def test_reports_must_be_released_before_submitting(client, session, world, documents_on):
    tid = await approved_thesis(client, session, world)
    await add_report(client, world, tid, release=False)
    aid = (await arrange(client, world, tid)).json()["id"]
    await board_add(
        client, world, aid, {"role": "chairperson", "faculty_id": str(world.sup_a2_faculty.id)}
    )
    await board_add(client, world, aid, EXAMINER)
    res = await act(client, world.exam_office, aid, "submit")
    assert res.json()["error"]["code"] == "viva_needs_reports"


async def test_board_rules_and_who_may_arrange(client, session, world, documents_on):
    tid, aid = await ready_arrangement(client, session, world)
    for user in (world.scholar_a1, world.meera, world.research_office, world.vice_chancellor):
        assert (await arrange(client, world, tid, user=user)).status_code == 403, user.email
    again = await arrange(client, world, tid)
    assert again.json()["error"]["code"] == "viva_already_arranged"

    for body, code in (
        ({"role": "member", "faculty_id": str(world.meera_faculty.id)}, "supervisor_on_board"),
        ({"role": "chairperson", "faculty_id": str(world.co_sup_faculty.id)}, "chairperson_taken"),
    ):
        res = await board_add(client, world, aid, body)
        assert res.json()["error"]["code"] == code, body
    inside_examiner = {"role": "external_examiner", "faculty_id": str(world.co_sup_faculty.id)}
    assert (await board_add(client, world, aid, inside_examiner)).status_code == 422

    # Once submitted, the board is fixed until it is sent back.
    await act(client, world.exam_office, aid, "submit")
    late = await board_add(
        client, world, aid, {"role": "member", "faculty_id": str(world.co_sup_faculty.id)}
    )
    assert late.json()["error"]["code"] == "workflow_violation"
    sent_back = await client.post(
        f"{API}/items/viva_arrangement/{aid}/send-back",
        headers=auth(world.vice_chancellor.id),
        json={"comment": "Add a second external examiner."},
    )
    assert sent_back.status_code == 200, sent_back.text
    member = {"role": "member", "faculty_id": str(world.co_sup_faculty.id)}
    assert (await board_add(client, world, aid, member)).status_code == 200
