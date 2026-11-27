"""Every upload passes ClamAV first (scanner.py; owner, 2026-11-27): infected files are refused
and, for files already in storage, removed with a marked row left as the record; when the
scanner cannot answer, uploads are refused rather than kept unscanned."""

import dataclasses

import pytest
from sqlalchemy import select

from app import scanner, storage
from app.config import Scanner, settings
from app.errors import ApiError
from app.models import AuditLog, FileRow, ScholarPhoto
from tests.conftest import auth
from tests.fake_clamd import EICAR, NAME
from tests.test_files import _upload, cleanup  # noqa: F401  (fixture)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_verdicts():
    assert scanner.verdict(b"stream: OK\0") is None
    assert scanner.verdict(b"stream: Win.Test.EICAR_HDB-1 FOUND\0") == "Win.Test.EICAR_HDB-1"
    with pytest.raises(ApiError) as limit:
        scanner.verdict(b"INSTREAM size limit exceeded. ERROR\0")
    assert limit.value.code == "scanner_unavailable"


async def test_an_infected_upload_is_removed_and_recorded(client, session, world, cleanup):  # noqa: F811
    body, put = await _upload(client, world.admin_a1, world.s_a1, cleanup, data=b"%PDF-" + EICAR)
    assert put.status_code == 200, put.text
    done = await client.post(
        f"/api/v1/files/{body['file_id']}/complete", headers=auth(world.admin_a1.id)
    )
    assert done.status_code == 422 and done.json()["error"]["code"] == "infected_file"
    assert NAME in done.json()["error"]["message"]

    row = await session.get(FileRow, body["file_id"])
    await session.refresh(row)
    assert row.status == "infected" and row.deleted_at is not None
    assert await storage.head(row.storage_key) is None  # gone from storage
    actions = await session.scalars(
        select(AuditLog.action).where(AuditLog.record_id == str(row.id))
    )
    assert "soft_delete" in set(actions)
    listed = await client.get(
        f"/api/v1/files?table_name=scholars&record_id={world.s_a1.id}",
        headers=auth(world.admin_a1.id),
    )
    assert body["file_id"] not in {f["id"] for f in listed.json()}


async def test_a_clean_upload_goes_through(client, world, cleanup):  # noqa: F811
    body, _ = await _upload(client, world.admin_a1, world.s_a1, cleanup)
    done = await client.post(
        f"/api/v1/files/{body['file_id']}/complete", headers=auth(world.admin_a1.id)
    )
    assert done.status_code == 200 and done.json()["status"] == "ready"


async def test_an_infected_image_is_never_kept(client, session, world):
    res = await client.put(
        f"/api/v1/scholars/{world.s_a1.id}/photo",
        headers={**auth(world.scholar_a1.id), "Content-Type": "image/png"},
        content=PNG + EICAR,
    )
    assert res.status_code == 422 and res.json()["error"]["code"] == "infected_file"
    assert await session.scalar(select(ScholarPhoto)) is None


async def test_no_scanner_no_upload(client, world, monkeypatch):
    dead = dataclasses.replace(settings, scanner=Scanner(host="127.0.0.1", port=1))
    monkeypatch.setattr(scanner, "settings", dead)
    res = await client.put(
        f"/api/v1/scholars/{world.s_a1.id}/photo",
        headers={**auth(world.scholar_a1.id), "Content-Type": "image/png"},
        content=PNG,
    )
    assert res.status_code == 503 and res.json()["error"]["code"] == "scanner_unavailable"
