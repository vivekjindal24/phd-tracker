import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import files, records, storage
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import soft_delete
from app.db import get_session
from app.enums import FileOwner
from app.errors import ApiError
from app.models import FileRow
from app.schemas import DownloadOut, FileOut, UploadIn, UploadOut

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/uploads", response_model=UploadOut, status_code=201)
async def start_upload(
    body: UploadIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> UploadOut:
    row, url = await files.start_upload(
        session,
        principal,
        body.table_name,
        body.record_id,
        body.file_name,
        body.content_type,
        body.size_bytes,
    )
    await session.commit()
    return UploadOut(
        file_id=row.id,
        upload_url=url,
        headers={"Content-Type": body.content_type},
        expires_in=storage.PRESIGN_SECONDS,
    )


@router.post("/{file_id}/complete", response_model=FileOut)
async def complete_upload(
    file_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> FileRow:
    row = await files.complete_upload(session, principal, await files.get_file(session, file_id))
    await session.commit()
    return row


@router.get("", response_model=list[FileOut])
async def list_files(
    table_name: FileOwner,
    record_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[FileRow]:
    await records.require_file_read(session, principal, table_name, record_id)
    rows = await session.scalars(
        select(FileRow)
        .where(
            FileRow.table_name == table_name,
            FileRow.record_id == record_id,
            FileRow.status == "ready",
            FileRow.deleted_at.is_(None),
        )
        .order_by(FileRow.created_at.desc())
    )
    return list(rows)


@router.get("/{file_id}/download", response_model=DownloadOut)
async def download(
    file_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> DownloadOut:
    row = await files.get_file(session, file_id)
    await records.require_file_read(session, principal, row.table_name, row.record_id)
    if row.status != "ready":
        raise ApiError(409, "upload_incomplete", "This file has not finished uploading.")
    return DownloadOut(
        url=storage.presign_get(row.storage_key, row.file_name), expires_in=storage.PRESIGN_SECONDS
    )


@router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Soft delete: the row disappears for everyone, the object stays (retention). Only while
    the owner record is still writable by the caller — an approved item's files are frozen."""
    row = await files.get_file(session, file_id)
    if row.table_name == "documents":
        raise ApiError(422, "versions_are_permanent", "Document versions cannot be removed.")
    await records.require_write(session, principal, row.table_name, row.record_id)
    if row.table_name == "thesis_submissions" and row.uploaded_by != principal.user_id:
        # Scholar and Library share the record: each removes only what it uploaded.
        raise ApiError(403, "forbidden", "Only whoever uploaded this file can remove it.")
    await soft_delete(session, principal, row)
    await session.commit()
