"""The PhD file's small records (PRD F17 "needs"): the order appointing each supervisor, the
scholar's father's name, national / international examiners, the comprehensive examination,
the assistantship line on a progress report, and named places for the employer NOC and the
entrance minutes."""

import uuid

from sqlalchemy import select

from app.models import FileRow
from tests.conftest import APR_SECTIONS, ASSESS, auth
from tests.test_thesis import approved_thesis, documents_on, evaluation  # noqa: F401

API = "/api/v1"


def scholar_url(world) -> str:
    return f"{API}/scholars/{world.s_a1.id}"


async def test_past_supervisors_stay_on_record(client, world):
    admin = auth(world.admin_a1.id)
    url = f"{scholar_url(world)}/supervision"
    (first,) = [
        a
        for a in (await client.get(url, headers=admin)).json()["appointments"]
        if a["role"] == "supervisor"
    ]
    assert first["faculty"]["name"] == "Meera" and first["ended_on"] is None
    order = {"appointed_on": "2022-03-01", "order_ref": "DRC/2022/9"}
    fixed = await client.patch(
        f"{API}/scholars/appointments/{first['id']}", headers=admin, json=order
    )
    assert fixed.status_code == 200, fixed.text

    # A new supervisor (an approved change) opens a new appointment; Meera's ends but stays.
    from tests.test_supervisor_changes import act, propose

    cid = (await propose(client, world, effective_on=None)).json()["id"]
    for user, action in (
        (world.admin_a1, "submit"),
        (world.admin_a1, "approve"),
        (world.research_office, "approve"),
    ):
        assert (await act(client, user, cid, action)).status_code == 200
    rows = [
        a
        for a in (await client.get(url, headers=admin)).json()["appointments"]
        if a["role"] == "supervisor"
    ]
    assert [(a["faculty"]["name"], a["ended_on"] is None) for a in rows] == [
        ("Sup A2", True),
        ("Meera", False),
    ]
    assert (rows[1]["appointed_on"], rows[1]["order_ref"]) == ("2022-03-01", "DRC/2022/9")
    # A past appointment's order can still be corrected, never to start after it ended.
    late = await client.patch(
        f"{API}/scholars/appointments/{rows[1]['id']}",
        headers=admin,
        json={"appointed_on": "2099-01-01"},
    )
    assert late.json()["error"]["code"] == "appointed_after_end"
    # So can the day it ended, but never on the current one, nor in the future.
    ended = await client.patch(
        f"{API}/scholars/appointments/{rows[1]['id']}",
        headers=admin,
        json={"ended_on": "2024-06-30"},
    )
    assert [a["ended_on"] for a in ended.json()["appointments"] if a["role"] == "supervisor"] == [
        None,
        "2024-06-30",
    ]
    for row, body, code in (
        (rows[0], {"ended_on": "2024-06-30"}, "appointment_current"),
        (rows[1], {"ended_on": "2099-01-01"}, "end_in_future"),
        (rows[1], {"ended_on": None}, "end_required"),
        (rows[1], {"ended_on": "2022-01-01"}, "appointed_after_end"),
    ):
        res = await client.patch(
            f"{API}/scholars/appointments/{row['id']}", headers=admin, json=body
        )
        assert res.json()["error"]["code"] == code, body

    # The scholar reads the history; only the admin over the unit corrects it.
    own = await client.get(url, headers=auth(world.scholar_a1.id))
    assert len(own.json()["appointments"]) >= 2 and not own.json()["can_manage"]
    refused = await client.patch(
        f"{API}/scholars/appointments/{rows[0]['id']}",
        headers=auth(world.scholar_a1.id),
        json=order,
    )
    assert refused.status_code == 403
    assert (await client.get(url, headers=auth(world.scholar_a2.id))).status_code == 403


async def test_fathers_name_is_personal(client, world):
    filled = await client.put(
        f"{API}/scholars/mine/profile",
        headers=auth(world.scholar_a1.id),
        json={"father_name": "Ramesh Patidar"},
    )
    assert filled.status_code == 200 and filled.json()["father_name"] == "Ramesh Patidar"
    again = await client.put(
        f"{API}/scholars/mine/profile",
        headers=auth(world.scholar_a1.id),
        json={"father_name": "Someone else"},
    )
    assert again.json()["error"]["code"] == "already_recorded"
    fixed = await client.patch(
        scholar_url(world), headers=auth(world.admin_a1.id), json={"father_name": "R. Patidar"}
    )
    assert fixed.json()["father_name"] == "R. Patidar"
    # A supervisor who is not also an admin or head reads the record, not personal data.
    a1b = f"{API}/scholars/{world.s_a1b.id}"
    await client.patch(a1b, headers=auth(world.admin_a1.id), json={"father_name": "K. Rao"})
    other = await client.get(a1b, headers=auth(world.sup_a2.id))
    assert other.status_code == 200 and other.json()["father_name"] is None
    assert (await client.get(a1b, headers=auth(world.admin_a1.id))).json()["father_name"] == (
        "K. Rao"
    )


async def test_examiner_origin(client, session, world, documents_on):  # noqa: F811
    tid = await approved_thesis(client, session, world)
    office = auth(world.exam_office.id)
    report = {
        "examiner_name": "Prof. Lee",
        "institution": "NUS",
        "origin": "international",
        "received_on": "2026-09-01",
        "recommendation": "accept",
    }
    res = await client.post(f"{API}/theses/{tid}/examiner-reports", headers=office, json=report)
    assert res.status_code == 200, res.text
    assert res.json()["reports"][0]["origin"] == "international"
    rid = res.json()["reports"][0]["id"]
    changed = await client.patch(
        f"{API}/examiner-reports/{rid}", headers=office, json={"origin": "national"}
    )
    assert changed.json()["reports"][0]["origin"] == "national"
    bad = await client.patch(f"{API}/examiner-reports/{rid}", headers=office, json={"origin": "x"})
    assert bad.status_code == 422


async def test_comprehensive_examination_attempts(client, world):
    url = f"{scholar_url(world)}/comprehensive"
    admin = auth(world.admin_a1.id)
    first = await client.post(
        url, headers=admin, json={"held_in": "2022-05-01", "result": "unsatisfactory"}
    )
    assert first.status_code == 200, first.text
    early = await client.post(
        url, headers=admin, json={"held_in": "2022-04-01", "result": "satisfactory"}
    )
    assert early.json()["error"]["code"] == "attempt_out_of_order"
    not_a_month = await client.post(
        url, headers=admin, json={"held_in": "2022-11-15", "result": "satisfactory"}
    )
    assert not_a_month.status_code == 422
    second = await client.post(
        url, headers=admin, json={"held_in": "2022-11-01", "result": "satisfactory"}
    )
    view = second.json()
    assert [(a["attempt"], a["result"]) for a in view["attempts"]] == [
        (1, "unsatisfactory"),
        (2, "satisfactory"),
    ]
    assert view["passed"] and view["can_manage"]
    third = await client.post(
        url, headers=admin, json={"held_in": "2023-05-01", "result": "satisfactory"}
    )
    assert third.json()["error"]["code"] == "comprehensive_passed"
    first_id = view["attempts"][0]["id"]
    out_of_turn = await client.delete(f"{API}/comprehensive-exams/{first_id}", headers=admin)
    assert out_of_turn.json()["error"]["code"] == "not_latest_attempt"

    own = await client.get(url, headers=auth(world.scholar_a1.id))
    assert own.status_code == 200 and not own.json()["can_manage"]
    for user in (world.scholar_a1, world.sup_a2, world.exam_office):
        res = await client.post(
            url, headers=auth(user.id), json={"held_in": "2023-05-01", "result": "satisfactory"}
        )
        assert res.status_code == 403, user.email
    assert (await client.get(url, headers=auth(world.scholar_a2.id))).status_code == 403


async def test_assistantship_line_is_stated_at_the_step(client, world):
    created = await client.post(
        f"{API}/reports",
        headers=auth(world.scholar_a1.id),
        json={
            "report_year": 2026,
            "period": "January-June",
            "summary": "Completed the survey of ponds across the district.",
            "sections": APR_SECTIONS,
        },
    )
    rid = created.json()["id"]
    url = f"{API}/reports/{rid}/assistantship"
    draft = await client.put(url, headers=auth(world.meera.id), json={"assistantship": "with"})
    assert draft.json()["error"]["code"] == "workflow_violation"  # nothing to act on yet
    await client.post(
        f"{API}/items/progress_report/{rid}/submit", headers=auth(world.scholar_a1.id)
    )
    by_scholar = await client.put(
        url, headers=auth(world.scholar_a1.id), json={"assistantship": "with"}
    )
    assert by_scholar.status_code == 422
    stated = await client.put(url, headers=auth(world.meera.id), json={"assistantship": "with"})
    assert stated.status_code == 200 and stated.json()["content"]["assistantship"] == "with"
    approved = await client.post(
        f"{API}/items/progress_report/{rid}/approve", headers=auth(world.meera.id), json=ASSESS
    )
    assert approved.status_code == 200, approved.text
    pdf = await client.get(
        f"{API}/internal/reports/{rid}/export-view", headers=auth(world.scholar_a1.id)
    )
    assert pdf.json()["assistantship"] == "with"


async def test_named_places_for_the_noc_and_entrance_minutes(client, session, world):
    body = {
        "table_name": "scholars",
        "record_id": str(world.s_a1.id),
        "file_name": "NOC.pdf",
        "content_type": "application/pdf",
        "size_bytes": 10,
        "slot": "employer_noc",
    }
    started = await client.post(f"{API}/files/uploads", headers=auth(world.admin_a1.id), json=body)
    assert started.status_code == 201, started.text
    row = await session.scalar(select(FileRow).where(FileRow.id == started.json()["file_id"]))
    assert row.slot == "employer_noc"
    elsewhere = await client.post(
        f"{API}/files/uploads",
        headers=auth(world.admin_a1.id),
        json=body | {"table_name": "meetings", "record_id": str(uuid.uuid4())},
    )
    assert elsewhere.status_code == 422
    # Listing one place shows only its files.
    for slot in ("employer_noc", "entrance_minutes"):
        session.add(
            FileRow(
                storage_key=f"scholars/{world.s_a1.id}/{uuid.uuid4()}/{slot}.pdf",
                file_name=f"{slot}.pdf",
                content_type="application/pdf",
                size_bytes=10,
                status="ready",
                uploaded_by=world.admin_a1.id,
                table_name="scholars",
                record_id=world.s_a1.id,
                slot=slot,
            )
        )
    await session.commit()
    listed = await client.get(
        f"{API}/files?table_name=scholars&record_id={world.s_a1.id}&slot=entrance_minutes",
        headers=auth(world.scholar_a1.id),
    )
    assert [f["file_name"] for f in listed.json()] == ["entrance_minutes.pdf"]
