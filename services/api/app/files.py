"""Files attached to records (PRD F13). Visibility is the OWNER record's (records.py): a file
is readable exactly when its owner is, writable where the owner is writable (SECURITY.md §3)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import records, storage
from app.auth.principal import Principal
from app.config import settings
from app.crud import insert, update
from app.errors import ApiError, forbidden
from app.models import FileRow

ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip",
        "text/plain",
        "text/csv",
        "image/png",
        "image/jpeg",
    }
)


async def start_upload(
    session: AsyncSession,
    principal: Principal,
    table: str,
    record_id: uuid.UUID,
    file_name: str,
    content_type: str,
    size_bytes: int,
) -> tuple[FileRow, str]:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ApiError(
            415,
            "unsupported_file_type",
            "Upload a PDF, Office document, image, text/CSV or zip file.",
        )
    limit = settings.s3.max_upload_bytes
    if size_bytes > limit:
        raise ApiError(413, "file_too_large", f"Files can be at most {limit // (1024 * 1024)} MB.")
    await records.require_write(session, principal, table, record_id)
    file_id = uuid.uuid4()
    key = f"{table}/{record_id}/{file_id}/{storage.safe_filename(file_name)}"
    row = await insert(
        session,
        principal,
        FileRow(
            id=file_id,
            storage_key=key,
            file_name=file_name,
            content_type=content_type,
            size_bytes=size_bytes,
            uploaded_by=principal.user_id,
            table_name=table,
            record_id=record_id,
        ),
    )
    return row, storage.presign_put(key, content_type, size_bytes)


async def get_file(session: AsyncSession, file_id: uuid.UUID) -> FileRow:
    row = await session.scalar(
        select(FileRow).where(FileRow.id == file_id, FileRow.deleted_at.is_(None))
    )
    if row is None:
        raise forbidden()  # existence is not leaked
    return row


async def complete_upload(session: AsyncSession, principal: Principal, row: FileRow) -> FileRow:
    """The browser says it uploaded: believe the bucket, not the browser."""
    if row.uploaded_by != principal.user_id:
        raise forbidden()
    if row.status == "ready":
        return row
    meta = await storage.head(row.storage_key)
    if meta is None:
        raise ApiError(409, "upload_missing", "The file did not arrive. Please upload it again.")
    if meta.get("ContentLength") != row.size_bytes:
        raise ApiError(409, "upload_mismatch", "The uploaded file differs from what was declared.")
    return await update(
        session, principal, row, {"status": "ready", "etag": str(meta.get("ETag", "")).strip('"')}
    )
