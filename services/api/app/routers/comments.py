"""Comment threads on records (PRD F13). Visible exactly when the record is."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import records
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import insert, soft_delete
from app.db import get_session
from app.enums import CommentTarget
from app.errors import forbidden
from app.models import Comment, Faculty, User
from app.notify import notify
from app.schemas import CommentIn, CommentOut

router = APIRouter(prefix="/comments", tags=["comments"])


@router.get("", response_model=list[CommentOut])
async def list_comments(
    table_name: CommentTarget,
    record_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[CommentOut]:
    await records.require_read(session, principal, table_name, record_id)
    rows = await session.execute(
        select(Comment, User.full_name)
        .join(User, User.id == Comment.author_id)
        .where(
            Comment.table_name == table_name,
            Comment.record_id == record_id,
            Comment.deleted_at.is_(None),
        )
        .order_by(Comment.created_at)
    )
    return [
        CommentOut(
            id=c.id,
            author=name,
            author_id=c.author_id,
            body=c.body,
            created_at=c.created_at,
            mine=c.author_id == principal.user_id,
        )
        for c, name in rows
    ]


@router.post("", response_model=CommentOut, status_code=201)
async def add_comment(
    body: CommentIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> CommentOut:
    scholar, link = await records.require_read(session, principal, body.table_name, body.record_id)
    comment = await insert(
        session,
        principal,
        Comment(
            table_name=body.table_name,
            record_id=body.record_id,
            author_id=principal.user_id,
            body=body.body,
        ),
    )
    # Tell the scholar and their supervisor (whoever of them didn't write it).
    supervisor_user = None
    if scholar.supervisor_id:
        supervisor_user = await session.scalar(
            select(Faculty.user_id).where(Faculty.id == scholar.supervisor_id)
        )
    recipients = [u for u in (scholar.user_id, supervisor_user) if u and u != principal.user_id]
    notify(
        session,
        recipients,
        "system",
        f"New comment from {principal.full_name}",
        body.body[:200],
        link,
    )
    await session.commit()
    return CommentOut(
        id=comment.id,
        author=principal.full_name,
        author_id=principal.user_id,
        body=comment.body,
        created_at=comment.created_at,
        mine=True,
    )


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    comment = await session.scalar(
        select(Comment).where(Comment.id == comment_id, Comment.deleted_at.is_(None))
    )
    if comment is None or comment.author_id != principal.user_id:
        raise forbidden()  # only the author removes a comment (soft delete)
    await soft_delete(session, principal, comment)
    await session.commit()
