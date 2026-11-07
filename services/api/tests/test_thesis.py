"""Thesis submission through its chain and what follows it (PRD M3, UX Flow 8), plus drafts
with versions. Examiner confidentiality is checked for every role that can see the thesis."""

import uuid

import pytest
from sqlalchemy import select

from app.models import FileRow, RoleAssignment, Scholar
from tests.conftest import auth
from tests.test_publications import enable


@pytest.fixture
async def documents_on(session, world):
    await enable(session, "documents")


async def ready_file(session, user, table: str, record_id) -> uuid.UUID:
    """A confirmed upload, as if the browser had PUT it to the bucket."""
    fid = uuid.uuid4()
    session.add(
        FileRow(
            id=fid,
            storage_key=f"{table}/{record_id}/{fid}/x.pdf",
            file_name="thesis.pdf",
            content_type="application/pdf",
            size_bytes=10,
            status="ready",
            uploaded_by=user.id,
            table_name=table,
            record_id=record_id,
        )
    )
    await session.commit()
    return fid


async def act(client, user, tid, action, body=None):
    return await client.post(
        f"/api/v1/items/thesis_submission/{tid}/{action}", headers=auth(user.id), json=body or {}
    )


async def record_title(client, session, world, title="On graphs", **fields):
    """The Research Office records the committee's decision, title and all."""
    scholar_id = await session.scalar(
        select(Scholar.id).where(Scholar.user_id == world.scholar_a1.id)
    )
    return await client.post(
        "/api/v1/milestones",
        headers=auth(world.research_office.id),
        json={
            "scholar_id": str(scholar_id),
            "milestone_type": "proposal_approval",
            "status": "Approved",
            "approval_body": "RDC",
            "approved_title": title,
            **fields,
        },
    )


async def new_thesis(client, session, world) -> str:
    assert (await record_title(client, session, world)).status_code == 201
    res = await client.post("/api/v1/theses", headers=auth(world.scholar_a1.id))
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def approved_thesis(client, session, world) -> str:
    tid = await new_thesis(client, session, world)
    await ready_file(session, world.scholar_a1, "thesis_submissions", tid)
    assert (await act(client, world.scholar_a1, tid, "submit")).status_code == 200
    assert (await act(client, world.meera, tid, "approve")).status_code == 200
    assert (await act(client, world.admin_a1, tid, "approve")).status_code == 200
    await client.put(
        f"/api/v1/theses/{tid}/plagiarism",
        headers=auth(world.library.id),
        json={"plagiarism_tool": "Turnitin", "plagiarism_score": 6.5},
    )
    assert (await act(client, world.library, tid, "approve")).status_code == 200
    await client.put(
        f"/api/v1/theses/{tid}/examiners",
        headers=auth(world.exam_office.id),
        json={"examiners": "Prof. X (IIT B); Prof. Y (IISc)"},
    )
    assert (await act(client, world.exam_office, tid, "approve")).status_code == 200
    res = await act(client, world.research_office, tid, "approve")
    assert res.json()["state"] == "approved"
    return tid


async def test_cannot_submit_without_the_thesis_file(client, session, world, documents_on):
    tid = await new_thesis(client, session, world)
    res = await act(client, world.scholar_a1, tid, "submit")
    assert res.status_code == 422
    assert "thesis file" in res.json()["error"]["message"]


async def test_one_live_thesis_per_scholar(client, session, world, documents_on):
    await new_thesis(client, session, world)
    res = await client.post("/api/v1/theses", headers=auth(world.scholar_a1.id))
    assert res.status_code == 409 and res.json()["error"]["code"] == "duplicate_thesis"


async def test_offices_must_fill_their_fields_before_approving(
    client, session, world, documents_on
):
    tid = await new_thesis(client, session, world)
    await ready_file(session, world.scholar_a1, "thesis_submissions", tid)
    await act(client, world.scholar_a1, tid, "submit")
    await act(client, world.meera, tid, "approve")
    await act(client, world.admin_a1, tid, "approve")
    res = await act(client, world.library, tid, "approve")
    assert res.status_code == 422
    assert "plagiarism" in res.json()["error"]["message"]
    # Someone not at the step still gets the ordinary refusal, not a hint about fields.
    other = await act(client, world.exam_office, tid, "approve")
    assert other.json()["error"]["message"].startswith("You cannot approve")
    early = await client.put(
        f"/api/v1/theses/{tid}/examiners",
        headers=auth(world.exam_office.id),
        json={"examiners": "Prof. X"},
    )
    assert early.status_code == 422


async def test_library_removes_only_its_own_certificate(client, session, world, documents_on):
    tid = await new_thesis(client, session, world)
    thesis_file = await ready_file(session, world.scholar_a1, "thesis_submissions", tid)
    await act(client, world.scholar_a1, tid, "submit")
    await act(client, world.meera, tid, "approve")
    await act(client, world.admin_a1, tid, "approve")
    certificate = await ready_file(session, world.library, "thesis_submissions", tid)

    scholars = await client.delete(f"/api/v1/files/{thesis_file}", headers=auth(world.library.id))
    assert scholars.status_code == 403
    own = await client.delete(f"/api/v1/files/{certificate}", headers=auth(world.library.id))
    assert own.status_code == 204


async def test_full_chain_moves_the_stage(client, session, world, documents_on):
    await approved_thesis(client, session, world)
    scholar = await session.scalar(select(Scholar).where(Scholar.id == world.s_a1.id))
    await session.refresh(scholar)
    assert scholar.stage == "Thesis Submitted"


async def test_examiner_names_hidden_in_the_thesis(client, session, world, documents_on):
    tid = await approved_thesis(client, session, world)
    for user in (world.scholar_a1, world.meera, world.admin_a1, world.library):
        content = (
            await client.get(f"/api/v1/items/thesis_submission/{tid}", headers=auth(user.id))
        ).json()["content"]
        assert content["examiners"] is None and content["examiners_hidden"], user.email
    for user in (world.exam_office, world.research_office, world.root_admin):
        content = (
            await client.get(f"/api/v1/items/thesis_submission/{tid}", headers=auth(user.id))
        ).json()["content"]
        assert content["examiners"].startswith("Prof. X"), user.email


async def evaluation(client, user, tid):
    return await client.get(f"/api/v1/theses/{tid}/evaluation", headers=auth(user.id))


async def test_reports_release_viva_and_deposit(client, session, world, documents_on):
    tid = await approved_thesis(client, session, world)
    report = {
        "examiner_name": "Prof. X",
        "institution": "IIT Bombay",
        "received_on": "2026-09-01",
        "recommendation": "minor_revision",
    }
    res = await client.post(
        f"/api/v1/theses/{tid}/examiner-reports", headers=auth(world.exam_office.id), json=report
    )
    assert res.status_code == 200
    assert res.json()["reports"][0]["examiner_name"] == "Prof. X"
    rid = res.json()["reports"][0]["id"]

    # Before release: the scholar sees nothing, the department sees it without the name.
    assert (await evaluation(client, world.scholar_a1, tid)).json()["reports"] == []
    dept = (await evaluation(client, world.admin_a1, tid)).json()
    assert dept["reports"][0]["examiner_name"] is None and dept["names_hidden"]
    # The report's file follows the same rule.
    files = await client.get(
        "/api/v1/files",
        headers=auth(world.scholar_a1.id),
        params={"table_name": "examiner_reports", "record_id": rid},
    )
    assert files.status_code == 403

    rel = await client.post(
        f"/api/v1/theses/{tid}/release-reports", headers=auth(world.exam_office.id)
    )
    assert rel.status_code == 200
    mine = (await evaluation(client, world.scholar_a1, tid)).json()
    assert [(r["recommendation"], r["examiner_name"]) for r in mine["reports"]] == [
        ("minor_revision", None)
    ]

    viva = {"held_on": "2026-10-10", "venue": "Senate Hall", "panel": "Prof. X", "outcome": "pass"}
    res = await client.post(
        f"/api/v1/theses/{tid}/vivas", headers=auth(world.exam_office.id), json=viva
    )
    assert res.status_code == 200
    scholar = await session.get(Scholar, world.s_a1.id)
    await session.refresh(scholar)
    assert scholar.stage == "Viva"
    # After the viva, names are no longer secret.
    mine = (await evaluation(client, world.scholar_a1, tid)).json()
    assert mine["reports"][0]["examiner_name"] == "Prof. X" and not mine["names_hidden"]

    dep = await client.put(
        f"/api/v1/theses/{tid}/deposit",
        headers=auth(world.library.id),
        json={"deposited_on": "2026-10-20", "handle_url": "https://shodhganga.inflibnet.ac.in/h/1"},
    )
    assert dep.status_code == 200
    assert (await evaluation(client, world.scholar_a1, tid)).json()["deposit"]["handle_url"]


VIVA = {"held_on": "2026-10-10", "outcome": "pass"}


async def test_nothing_recorded_before_approval(client, session, world, documents_on):
    tid = await new_thesis(client, session, world)
    early = await client.post(
        f"/api/v1/theses/{tid}/vivas", headers=auth(world.exam_office.id), json=VIVA
    )
    assert early.status_code == 422 and early.json()["error"]["code"] == "thesis_not_approved"


async def test_post_approval_negatives(client, session, world, documents_on):
    viva = VIVA
    tid = await approved_thesis(client, session, world)
    for user, path in (
        (world.scholar_a1, "vivas"),
        (world.library, "vivas"),
        (world.meera, "examiner-reports"),
    ):
        res = await client.post(
            f"/api/v1/theses/{tid}/{path}",
            headers=auth(user.id),
            json=viva
            | {"examiner_name": "x", "received_on": "2026-09-01", "recommendation": "accept"},
        )
        assert res.status_code == 403, (user.email, path)
    dep = await client.put(
        f"/api/v1/theses/{tid}/deposit",
        headers=auth(world.exam_office.id),
        json={"deposited_on": "2026-10-20", "handle_url": "https://x.org/1"},
    )
    assert dep.status_code == 403
    for user in (world.scholar_a2, world.hod_b1):
        assert (await evaluation(client, user, tid)).status_code == 403


async def test_documents_are_private_to_scholar_and_supervisor(
    client, session, world, documents_on
):
    res = await client.post(
        "/api/v1/documents",
        headers=auth(world.scholar_a1.id),
        json={"title": "Chapter 2", "doc_kind": "chapter"},
    )
    assert res.status_code == 201
    did = res.json()["id"]
    fid = await ready_file(session, world.scholar_a1, "documents", did)
    res = await client.post(
        f"/api/v1/documents/{did}/versions",
        headers=auth(world.scholar_a1.id),
        json={"file_id": str(fid), "note": "First full draft"},
    )
    assert res.status_code == 201 and res.json()["versions"][0]["version_no"] == 1
    again = await client.post(
        f"/api/v1/documents/{did}/versions",
        headers=auth(world.scholar_a1.id),
        json={"file_id": str(fid)},
    )
    assert again.status_code == 409  # one file, one version

    seen = await client.get(f"/api/v1/documents/{did}", headers=auth(world.meera.id))
    assert seen.status_code == 200 and seen.json()["can_edit"] is False
    for user in (world.dean_a, world.admin_a1, world.research_office, world.scholar_a2):
        res = await client.get(f"/api/v1/documents/{did}", headers=auth(user.id))
        assert res.status_code == 403, user.email
    comment = await client.post(
        "/api/v1/comments",
        headers=auth(world.meera.id),
        json={"table_name": "documents", "record_id": did, "body": "Tighten section 2.3."},
    )
    assert comment.status_code == 201
    removed = await client.delete(f"/api/v1/files/{fid}", headers=auth(world.scholar_a1.id))
    assert removed.status_code == 422


REPORT = {"examiner_name": "Prof. X", "received_on": "2026-09-01", "recommendation": "accept"}


async def add_report(client, world, tid, *, release: bool = True) -> str:
    res = await client.post(
        f"/api/v1/theses/{tid}/examiner-reports", headers=auth(world.exam_office.id), json=REPORT
    )
    assert res.status_code == 200, res.text
    if release:
        rel = await client.post(
            f"/api/v1/theses/{tid}/release-reports", headers=auth(world.exam_office.id)
        )
        assert rel.status_code == 200, rel.text
    return res.json()["reports"][-1]["id"]


async def record_viva(client, world, tid, **body):
    return await client.post(
        f"/api/v1/theses/{tid}/vivas", headers=auth(world.exam_office.id), json=VIVA | body
    )


async def test_supervisor_who_is_also_head_waits_for_release(client, session, world, documents_on):
    tid = await approved_thesis(client, session, world)  # Meera: supervisor + HoD + admin of A1
    rid = await add_report(client, world, tid, release=False)

    mine = (await evaluation(client, world.meera, tid)).json()
    assert mine["reports"] == [] and mine["unreleased_count"] == 0
    files = await client.get(
        "/api/v1/files",
        headers=auth(world.meera.id),
        params={"table_name": "examiner_reports", "record_id": rid},
    )
    assert files.status_code == 403
    assert len((await evaluation(client, world.admin_a1, tid)).json()["reports"]) == 1

    await client.post(f"/api/v1/theses/{tid}/release-reports", headers=auth(world.exam_office.id))
    assert len((await evaluation(client, world.meera, tid)).json()["reports"]) == 1


@pytest.mark.parametrize("office", ["exam_office", "research_office", "library"])
async def test_supervisor_in_an_office_waits_for_release(
    client, session, world, documents_on, office
):
    tid = await approved_thesis(client, session, world)
    rid = await add_report(client, world, tid, release=False)
    session.add(RoleAssignment(user_id=world.meera.id, role=office))  # supervises scholar_a1
    await session.commit()

    mine = (await evaluation(client, world.meera, tid)).json()
    assert mine["reports"] == [] and mine["unreleased_count"] == 0
    files = await client.get(
        "/api/v1/files",
        headers=auth(world.meera.id),
        params={"table_name": "examiner_reports", "record_id": rid},
    )
    assert files.status_code == 403
    content = (
        await client.get(f"/api/v1/items/thesis_submission/{tid}", headers=auth(world.meera.id))
    ).json()["content"]
    assert content["examiners"] is None and content["examiners_hidden"]


async def test_supervisor_in_the_exam_office_cannot_touch_own_scholars_reports(
    client, session, world, documents_on
):
    tid = await approved_thesis(client, session, world)
    await add_report(client, world, tid, release=False)
    session.add(RoleAssignment(user_id=world.meera.id, role="exam_office"))
    await session.commit()

    res = await client.post(f"/api/v1/theses/{tid}/release-reports", headers=auth(world.meera.id))
    assert res.status_code == 403 and res.json()["error"]["code"] == "own_scholar"
    assert (await evaluation(client, world.meera, tid)).json()["reports"] == []


async def test_viva_cannot_be_dated_in_the_future(client, session, world, documents_on):
    tid = await approved_thesis(client, session, world)
    await add_report(client, world, tid)
    res = await record_viva(client, world, tid, held_on="2099-01-01")
    assert res.status_code == 422 and res.json()["error"]["code"] == "viva_in_future"
    scholar = await session.get(Scholar, world.s_a1.id)
    await session.refresh(scholar)
    assert scholar.stage != "Viva"


async def test_viva_waits_for_released_reports(client, session, world, documents_on):
    tid = await approved_thesis(client, session, world)
    res = await record_viva(client, world, tid)
    assert res.status_code == 422 and res.json()["error"]["code"] == "viva_needs_reports"
    await add_report(client, world, tid, release=False)
    res = await record_viva(client, world, tid)
    assert res.status_code == 422 and res.json()["error"]["code"] == "viva_needs_reports"
    assert (await evaluation(client, world.exam_office, tid)).json()["viva_block"]


async def test_pass_and_fail_end_the_viva_record(client, session, world, documents_on):
    tid = await approved_thesis(client, session, world)
    await add_report(client, world, tid)
    assert (await evaluation(client, world.exam_office, tid)).json()["viva_block"] is None
    assert (await record_viva(client, world, tid, outcome="redefend")).status_code == 200
    assert (await record_viva(client, world, tid, outcome="fail")).status_code == 200
    res = await record_viva(client, world, tid, outcome="pass")
    assert res.status_code == 422 and res.json()["error"]["code"] == "viva_concluded"


async def test_viva_correction_keeps_the_rules(client, session, world, documents_on):
    tid = await approved_thesis(client, session, world)
    await add_report(client, world, tid)
    await record_viva(client, world, tid, outcome="redefend")
    second = await record_viva(client, world, tid, outcome="pass")
    by_outcome = {v["outcome"]: v for v in second.json()["vivas"]}
    first, last = by_outcome["redefend"], by_outcome["pass"]
    headers = auth(world.exam_office.id)
    url = f"/api/v1/vivas/{first['id']}"
    res = await client.patch(url, json={"held_on": "2099-01-01"}, headers=headers)
    assert res.status_code == 422 and res.json()["error"]["code"] == "viva_in_future"
    res = await client.patch(url, json={"outcome": "fail"}, headers=headers)
    assert res.status_code == 422 and res.json()["error"]["code"] == "viva_concluded"
    res = await client.patch(
        f"/api/v1/vivas/{last['id']}", json={"outcome": "fail"}, headers=headers
    )
    assert res.status_code == 200
