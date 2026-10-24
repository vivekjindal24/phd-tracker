"""Thesis submission through its chain and what follows it (PRD M3, UX Flow 8), plus drafts
with versions. Examiner confidentiality is checked for every role that can see the thesis."""

import uuid

import pytest
from sqlalchemy import select

from app.models import FileRow, Scholar
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


async def new_thesis(client, world) -> str:
    res = await client.post(
        "/api/v1/theses", headers=auth(world.scholar_a1.id), json={"title": "On graphs"}
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def approved_thesis(client, session, world) -> str:
    tid = await new_thesis(client, world)
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


async def test_cannot_submit_without_the_thesis_file(client, world, documents_on):
    tid = await new_thesis(client, world)
    res = await act(client, world.scholar_a1, tid, "submit")
    assert res.status_code == 422
    assert "thesis file" in res.json()["error"]["message"]


async def test_one_live_thesis_per_scholar(client, world, documents_on):
    await new_thesis(client, world)
    res = await client.post(
        "/api/v1/theses", headers=auth(world.scholar_a1.id), json={"title": "Again"}
    )
    assert res.status_code == 409 and res.json()["error"]["code"] == "duplicate_thesis"


async def test_offices_must_fill_their_fields_before_approving(
    client, session, world, documents_on
):
    tid = await new_thesis(client, world)
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
    tid = await new_thesis(client, world)
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


async def test_nothing_recorded_before_approval(client, world, documents_on):
    tid = await new_thesis(client, world)
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
