"""Flat per-record comment threads.

There is no MATRIX row for comments: visibility is entirely the target record's
get_or_403 — you comment on, and read comments of, exactly what you can already see.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import Actor, get_actor
from ..crud import insert, soft_delete
from ..db import get_db
from ..errors import ApiError
from ..models import TARGET_MODELS, Comment
from ..rbac import get_or_403
from ..schemas import CommentIn, CommentOut

router = APIRouter(prefix="/comments", tags=["comments"])

CommentTable = Literal["scholars", "meetings", "progress_reports", "milestones"]


async def _visible_target(
	db: AsyncSession, actor: Actor, table_name: CommentTable, record_id: UUID
) -> None:
	"""The single visibility gate for every comment route."""
	await get_or_403(db, TARGET_MODELS[table_name], record_id, actor)


@router.get("", response_model=list[CommentOut])
async def list_comments(
	table_name: CommentTable,
	record_id: UUID,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> list[Comment]:
	await _visible_target(db, actor, table_name, record_id)
	stmt = (
		select(Comment)
		.where(
			Comment.table_name == table_name,
			Comment.record_id == record_id,
			Comment.deleted_at.is_(None),
		)
		.order_by(Comment.created_at)
	)
	return (await db.scalars(stmt)).all()


@router.post("", response_model=CommentOut, status_code=201)
async def create_comment(
	body: CommentIn,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> Comment:
	await _visible_target(db, actor, body.table_name, body.record_id)
	return await insert(
		db,
		Comment(
			table_name=body.table_name,
			record_id=body.record_id,
			author_id=actor.user.id,
			body=body.body,
		),
		actor,
		"comments",
	)


@router.delete("/{id}", status_code=204)
async def delete_comment(
	id: UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> None:
	comment = await db.scalar(select(Comment).where(Comment.id == id, Comment.deleted_at.is_(None)))
	if comment is None:
		raise ApiError(404, "not_found", "Comment not found")
	await _visible_target(db, actor, comment.table_name, comment.record_id)
	if comment.author_id != actor.user.id and actor.role != "admin":
		raise ApiError(403, "permission_denied", "Only the author or an admin may delete a comment")
	await soft_delete(db, comment, actor)