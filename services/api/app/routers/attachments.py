"""File attachments — bytes in Postgres (bytea), capped at 2MB per file.

Same visibility model as comments: the target record's get_or_403 gates every
route. Download returns raw bytes (no response_model); the list is metadata-only.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import Actor, get_actor
from ..crud import insert, soft_delete
from ..db import get_db
from ..errors import ApiError
from ..models import TARGET_MODELS, Attachment
from ..rbac import get_or_403
from ..schemas import AttachmentOut

router = APIRouter(prefix="/attachments", tags=["attachments"])

MAX_BYTES = 2 * 1024 * 1024

AttachmentTable = Literal["scholars", "meetings", "progress_reports", "milestones"]


async def _visible_target(
	db: AsyncSession, actor: Actor, table_name: AttachmentTable, record_id: UUID
) -> None:
	await get_or_403(db, TARGET_MODELS[table_name], record_id, actor)


async def _get_attachment(db: AsyncSession, id: UUID) -> Attachment:
	att = await db.scalar(
		select(Attachment).where(Attachment.id == id, Attachment.deleted_at.is_(None))
	)
	if att is None:
		raise ApiError(404, "not_found", "Attachment not found")
	return att


def _safe_filename(name: str) -> str:
	"""Header-injection guard: keep it a single token, quote the rest."""
	return name.replace('"', "'").replace("\r", " ").replace("\n", " ")[:200]


@router.get("", response_model=list[AttachmentOut])
async def list_attachments(
	table_name: AttachmentTable,
	record_id: UUID,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> list[Attachment]:
	await _visible_target(db, actor, table_name, record_id)
	stmt = select(Attachment).where(
		Attachment.table_name == table_name,
		Attachment.record_id == record_id,
		Attachment.deleted_at.is_(None),
	)
	return (await db.scalars(stmt)).all()


@router.post("", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
	file: UploadFile,
	table_name: AttachmentTable = Form(...),
	record_id: UUID = Form(...),
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> Attachment:
	await _visible_target(db, actor, table_name, record_id)
	content = await file.read()
	if len(content) > MAX_BYTES:
		raise ApiError(413, "too_large", "Attachments are capped at 2MB")
	att = Attachment(
		table_name=table_name,
		record_id=record_id,
		file_name=file.filename or "upload",
		content_type=file.content_type or "application/octet-stream",
		size_bytes=len(content),
		content=content,
		uploaded_by=actor.user.id,
	)
	return await insert(db, att, actor, "attachments")


@router.get("/{id}/download")
async def download_attachment(
	id: UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> Response:
	att = await _get_attachment(db, id)
	await _visible_target(db, actor, att.table_name, att.record_id)
	return Response(
		bytes(att.content),  # psycopg3 hands back a memoryview; Response wants bytes
		media_type=att.content_type,
		headers={
			"Content-Disposition": f'attachment; filename="{_safe_filename(att.file_name)}"'
		},
	)


@router.delete("/{id}", status_code=204)
async def delete_attachment(
	id: UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> None:
	att = await _get_attachment(db, id)
	await _visible_target(db, actor, att.table_name, att.record_id)
	if att.uploaded_by != actor.user.id and actor.role != "admin":
		raise ApiError(403, "permission_denied", "Only the uploader or an admin may delete this file")
	await soft_delete(db, att, actor)