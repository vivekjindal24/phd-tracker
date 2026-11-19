"""Signed copies of the PhD file's forms (PRD F17b), against the real test bucket (TESTING.md
§1.5): the supervisor uploads, an admin over the unit or the Research Office approves."""

import uuid

import httpx
import pytest
from sqlalchemy import select

from app import storage
from app.db import SessionLocal
from app.models import FileRow
from tests.conftest import auth
from tests.test_thesis import approved_thesis, documents_on  # noqa: F401

API = "/api/v1"
PDF = b"%PDF-1.4\n% a signed form\n"


@pytest.fixture
async def cleanup():
    keys: list[str] = []
    yield keys
    for key in keys:
        await storage.delete(key)


def entry(view):
    (e,) = next(a for a in view["annexures"] if a["key"] == "comprehensive")["entries"]
    return e


def copy_of(view):
    (paper,) = entry(view)["papers"]
    return paper["copy"]


async def file_view(client, world, user, scholar=None):
    res = await client.get(
        f"{API}/internal/scholars/{(scholar or world.s_a1b).id}/phd-file", headers=auth(user.id)
    )
    assert res.status_code == 200, res.text
    return res.json()


async def upload_scan(client, user, copy_id, cleanup) -> str:
    start = await client.post(
        f"{API}/files/uploads",
        headers=auth(user.id),
        json={
            "table_name": "signed_copies",
            "record_id": copy_id,
            "file_name": "comprehensive-signed.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(PDF),
        },
    )
    assert start.status_code == 201, start.text
    body = start.json()
    async with SessionLocal() as s:
        cleanup.append(
            await s.scalar(select(FileRow.storage_key).where(FileRow.id == body["file_id"]))
        )
    async with httpx.AsyncClient() as raw:
        assert (await raw.put(body["upload_url"], content=PDF, headers=body["headers"])).is_success
    done = await client.post(f"{API}/files/{body['file_id']}/complete", headers=auth(user.id))
    assert done.status_code == 200, done.text
    return body["file_id"]


async def test_supervisor_uploads_and_an_admin_approves(client, world, cleanup):
    await client.post(
        f"{API}/scholars/{world.s_a1b.id}/comprehensive",
        headers=auth(world.admin_a1.id),
        json={"held_in": "2024-05-01", "result": "satisfactory"},
    )
    view = await file_view(client, world, world.sup_a2)
    (paper,) = entry(view)["papers"]
    assert view["handles_copies"] and paper["may_upload"] and not paper["may_approve"]
    record = entry(view)["record"]
    new = {"annexure": "comprehensive", "record_id": record}
    copies = f"{API}/scholars/{world.s_a1b.id}/signed-copies"

    # Not the scholar, not an outside supervisor; and only for an entry of this file.
    for outsider in (world.scholar_a1b, world.sup_b1):
        assert (await client.post(copies, json=new, headers=auth(outsider.id))).status_code == 403
    wrong = {"annexure": "comprehensive", "record_id": str(uuid.uuid4())}
    assert (await client.post(copies, json=wrong, headers=auth(world.sup_a2.id))).status_code == 404

    made = await client.post(copies, json=new, headers=auth(world.sup_a2.id))
    assert made.status_code == 201, made.text
    copy_id = made.json()["id"]
    file_id = await upload_scan(client, world.sup_a2, copy_id, cleanup)
    again = await client.post(
        f"{API}/files/uploads",
        headers=auth(world.sup_a2.id),
        json={
            "table_name": "signed_copies",
            "record_id": copy_id,
            "file_name": "x.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(PDF),
        },
    )
    assert again.status_code == 409  # one scan per copy
    word = {
        "table_name": "signed_copies",
        "record_id": copy_id,
        "file_name": "x.docx",
        "content_type": "application/msword",
        "size_bytes": 10,
    }
    res = await client.post(f"{API}/files/uploads", headers=auth(world.sup_a2.id), json=word)
    assert res.status_code == 415  # the file holds pages: a PDF or a photo only

    # Waiting: listed on the entry, not yet signed, no scan for the export.
    copy = copy_of(await file_view(client, world, world.sup_a2))
    assert copy["id"] == copy_id and copy["approved_at"] is None and copy["scan_url"] is None
    assert entry(await file_view(client, world, world.sup_a2))["signed"] is None
    inbox = (await client.get(f"{API}/notifications", headers=auth(world.admin_a1.id))).json()
    assert any("signed copy" in n["title"] for n in inbox)

    approve = f"{API}/signed-copies/{copy_id}/approve"
    assert (await client.post(approve, headers=auth(world.sup_a2.id))).status_code == 403
    assert (await client.post(approve, headers=auth(world.admin_a1.id))).status_code == 204

    e = entry(await file_view(client, world, world.research_office))
    assert e["signed"] is True and e["papers"][0]["copy"]["scan_url"]
    # The scan reads like its entry: the scholar yes, another department's scholar no.
    dl = f"{API}/files/{file_id}/download"
    assert (await client.get(dl, headers=auth(world.scholar_a1b.id))).status_code == 200
    assert (await client.get(dl, headers=auth(world.scholar_b1.id))).status_code == 403
    # Approved: the supervisor can no longer take it back; the admin can.
    gone = f"{API}/signed-copies/{copy_id}"
    assert (await client.delete(gone, headers=auth(world.sup_a2.id))).status_code == 403
    assert (await client.delete(gone, headers=auth(world.admin_a1.id))).status_code == 204
    assert copy_of(await file_view(client, world, world.sup_a2)) is None


async def test_the_office_upload_counts_at_once(client, world, cleanup):
    await client.post(
        f"{API}/scholars/{world.s_a1b.id}/comprehensive",
        headers=auth(world.admin_a1.id),
        json={"held_in": "2024-05-01", "result": "satisfactory"},
    )
    record = entry(await file_view(client, world, world.research_office))["record"]
    made = await client.post(
        f"{API}/scholars/{world.s_a1b.id}/signed-copies",
        json={"annexure": "comprehensive", "record_id": record},
        headers=auth(world.research_office.id),
    )
    assert made.status_code == 201, made.text
    await upload_scan(client, world.research_office, made.json()["id"], cleanup)
    e = entry(await file_view(client, world, world.research_office))
    assert e["signed"] is True and e["papers"][0]["copy"]["approved_at"]


async def test_each_paper_has_its_place_and_examiner_papers_stay_with_the_offices(
    client,
    session,
    world,
    cleanup,
    documents_on,  # noqa: F811
):
    tid = await approved_thesis(client, session, world)

    def thesis_papers(view, annexure):
        part = next(a for a in view["annexures"] if a["key"] == annexure)
        return [e for e in part["entries"] if e["record"] == tid]

    office = await file_view(client, world, world.research_office, world.s_a1)
    (submitted,) = thesis_papers(office, "submission")
    assert [p["kind"] for p in submitted["papers"]] == ["signed_copy", "fee_due", "corrections"]
    (letters,) = thesis_papers(office, "examiners")
    assert letters["papers"][0]["label"] == "Panel of examiners"
    # Never the scholar or the supervisor — not even a supervisor who is also the unit's admin.
    for user in (world.scholar_a1, world.meera):
        assert thesis_papers(await file_view(client, world, user, world.s_a1), "examiners") == []
    for user in (world.exam_office, world.admin_a1):
        assert thesis_papers(await file_view(client, world, user, world.s_a1), "examiners")

    copies = f"{API}/scholars/{world.s_a1.id}/signed-copies"
    panel = {"annexure": "examiners", "record_id": tid, "kind": "examiner_panel"}
    assert (await client.post(copies, json=panel, headers=auth(world.meera.id))).status_code == 404
    mixed = {**panel, "kind": "fee_due"}  # a paper the entry does not hold
    res = await client.post(copies, json=mixed, headers=auth(world.research_office.id))
    assert res.status_code == 422 and res.json()["error"]["code"] == "wrong_paper"
    made = await client.post(copies, json=panel, headers=auth(world.exam_office.id))
    assert made.status_code == 201, made.text
    file_id = await upload_scan(client, world.exam_office, made.json()["id"], cleanup)
    (letters,) = thesis_papers(
        await file_view(client, world, world.admin_a1, world.s_a1), "examiners"
    )
    assert letters["papers"][0]["copy"]["approved_at"]  # the Exam Office's own counts at once
    dl = f"{API}/files/{file_id}/download"
    assert (await client.get(dl, headers=auth(world.meera.id))).status_code == 403
    assert (await client.get(dl, headers=auth(world.scholar_a1.id))).status_code == 403
