"""File uploads against the real R2 test bucket (TESTING.md §1.5) — no S3 mocks."""

import httpx
import pytest
from sqlalchemy import select

from app import storage
from app.db import SessionLocal
from app.models import FileRow
from tests.conftest import auth

PDF = b"%PDF-1.4\n% Anveshan test file\n"


@pytest.fixture
async def cleanup():
    keys: list[str] = []
    yield keys
    for key in keys:
        await storage.delete(key)


def upload_body(scholar_id, size=len(PDF), content_type="application/pdf"):
    return {
        "table_name": "scholars",
        "record_id": str(scholar_id),
        "file_name": "Admission letter.pdf",
        "content_type": content_type,
        "size_bytes": size,
    }


async def _upload(client, user, scholar, cleanup, data=PDF):
    start = await client.post(
        "/api/v1/files/uploads", json=upload_body(scholar.id, len(data)), headers=auth(user.id)
    )
    assert start.status_code == 201, start.text
    body = start.json()
    async with httpx.AsyncClient() as raw:
        put = await raw.put(body["upload_url"], content=data, headers=body["headers"])
    async with SessionLocal() as s:
        cleanup.append(
            await s.scalar(select(FileRow.storage_key).where(FileRow.id == body["file_id"]))
        )
    return body, put


async def test_admin_uploads_and_owner_scope_controls_access(client, world, cleanup):
    body, put = await _upload(client, world.admin_a1, world.s_a1, cleanup)
    assert put.status_code == 200, put.text
    done = await client.post(
        f"/api/v1/files/{body['file_id']}/complete", headers=auth(world.admin_a1.id)
    )
    assert done.status_code == 200 and done.json()["status"] == "ready"

    # The scholar can see and download files on their own record...
    listed = await client.get(
        f"/api/v1/files?table_name=scholars&record_id={world.s_a1.id}",
        headers=auth(world.scholar_a1.id),
    )
    assert [f["file_name"] for f in listed.json()] == ["Admission letter.pdf"]
    link = await client.get(
        f"/api/v1/files/{body['file_id']}/download", headers=auth(world.scholar_a1.id)
    )
    async with httpx.AsyncClient() as raw:
        got = await raw.get(link.json()["url"])
    assert got.content == PDF
    assert got.headers["content-disposition"].startswith("attachment;")

    # ...another scholar and another department's head cannot, not even the link.
    for outsider in (world.scholar_b1, world.hod_b1):
        res = await client.get(
            f"/api/v1/files/{body['file_id']}/download", headers=auth(outsider.id)
        )
        assert res.status_code == 403


async def test_size_is_bound_into_the_signed_upload(client, world, cleanup):
    start = await client.post(
        "/api/v1/files/uploads",
        json=upload_body(world.s_a1.id, 10),
        headers=auth(world.admin_a1.id),
    )
    body = start.json()
    async with httpx.AsyncClient() as raw:
        put = await raw.put(body["upload_url"], content=b"x" * 999, headers=body["headers"])
    assert put.status_code in (400, 403)  # the bucket rejects a different size


async def test_complete_before_upload_is_409(client, world):
    start = await client.post(
        "/api/v1/files/uploads", json=upload_body(world.s_a1.id), headers=auth(world.admin_a1.id)
    )
    res = await client.post(
        f"/api/v1/files/{start.json()['file_id']}/complete", headers=auth(world.admin_a1.id)
    )
    assert res.json()["error"]["code"] == "upload_missing"
    # Not ready -> not listed, not downloadable.
    dl = await client.get(
        f"/api/v1/files/{start.json()['file_id']}/download", headers=auth(world.admin_a1.id)
    )
    assert dl.json()["error"]["code"] == "upload_incomplete"


@pytest.mark.parametrize(
    ("size", "ctype", "status", "code"),
    [
        (100, "text/html", 415, "unsupported_file_type"),
        (10**12, "application/pdf", 413, "file_too_large"),
    ],
)
async def test_type_and_size_limits(client, world, size, ctype, status, code):
    res = await client.post(
        "/api/v1/files/uploads",
        json=upload_body(world.s_a1.id, size, ctype),
        headers=auth(world.admin_a1.id),
    )
    assert (res.status_code, res.json()["error"]["code"]) == (status, code)


@pytest.mark.parametrize("who", ["scholar_a1", "meera", "dean_a", "hod_b1"])
async def test_only_an_admin_over_the_unit_may_attach(client, world, who):
    # Meera is HoD *and* admin of A1 -> allowed; the rest are readers or out of scope.
    res = await client.post(
        "/api/v1/files/uploads",
        json=upload_body(world.s_a1.id),
        headers=auth(getattr(world, who).id),
    )
    assert res.status_code == (201 if who == "meera" else 403)


async def test_only_uploader_completes_and_delete_hides(client, world, cleanup):
    body, _ = await _upload(client, world.admin_a1, world.s_a1, cleanup)
    other = await client.post(
        f"/api/v1/files/{body['file_id']}/complete", headers=auth(world.root_admin.id)
    )
    assert other.status_code == 403
    await client.post(f"/api/v1/files/{body['file_id']}/complete", headers=auth(world.admin_a1.id))
    gone = await client.delete(f"/api/v1/files/{body['file_id']}", headers=auth(world.admin_a1.id))
    assert gone.status_code == 204
    listed = await client.get(
        f"/api/v1/files?table_name=scholars&record_id={world.s_a1.id}",
        headers=auth(world.admin_a1.id),
    )
    assert listed.json() == []
