"""Signed copies (PRD F17b): the scan of a form signed on paper, put in the PhD file in place of
the generated page. One per entry of the file, keyed by the annexure and the record behind it.

Who uploads: an admin over the scholar's unit, the Research Office, or the scholar's supervisor
(co-supervisor too where co-supervision is on). Who approves: the admin or the Research Office
(scope.can_record); their own uploads count as approved at once. A supervisor's upload waits, and
the keepers are told. Everyone who uploads, approves or removes is in the audit log (crud.py).
Reading a copy follows the entry it stands for: whoever sees that entry in the file sees it."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import phd_file, scope, signatures, storage
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.errors import ApiError, forbidden
from app.models import FileRow, Scholar, SignedCopy, User
from app.notify import notify


def supervises(principal: Principal, scholar: Scholar) -> bool:
    return scholar.supervisor_id in principal.supervises or (
        principal.co_supervision != "off"
        and principal.faculty_id is not None
        and scholar.co_supervisor_id == principal.faculty_id
    )


async def may_upload(session: AsyncSession, principal: Principal, scholar: Scholar) -> bool:
    return supervises(principal, scholar) or await scope.can_record(session, principal, scholar)


async def create(
    session: AsyncSession,
    principal: Principal,
    scholar_id: uuid.UUID,
    annexure: str,
    record_id: uuid.UUID,
) -> SignedCopy:
    """A place for the scan; the browser then uploads it as a file on this row (files.py)."""
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id)
    if not await may_upload(session, principal, scholar):
        raise forbidden()
    if not await phd_file.sees_entry(session, principal, scholar, annexure, record_id):
        raise ApiError(404, "not_found", "That entry is not in this scholar's file.")
    keeper = await scope.can_record(session, principal, scholar)
    now = datetime.now(UTC)
    copy = await insert(
        session,
        principal,
        SignedCopy(
            scholar_id=scholar.id,
            annexure=annexure,
            record_id=record_id,
            uploaded_by=principal.user_id,
            approved_by=principal.user_id if keeper else None,
            approved_at=now if keeper else None,
        ),
    )
    if not keeper:
        notify(
            session,
            await signatures.keepers(session, scholar.user_id),
            "system",
            f"A signed copy from {principal.full_name} waits for your approval",
            "Check the scan against the paper form, then approve it.",
            f"/scholars/{scholar.id}",
        )
    return copy


async def _live(session: AsyncSession, copy_id: uuid.UUID) -> tuple[SignedCopy, Scholar]:
    row = (
        await session.execute(
            select(SignedCopy, Scholar)
            .join(Scholar, Scholar.id == SignedCopy.scholar_id)
            .where(SignedCopy.id == copy_id, SignedCopy.deleted_at.is_(None))
        )
    ).first()
    if row is None:
        raise forbidden()  # existence is not leaked
    return row[0], row[1]


async def require_read(session: AsyncSession, principal: Principal, copy_id: uuid.UUID) -> None:
    copy, scholar = await _live(session, copy_id)
    await scope.get_scholar_or_403(session, principal, scholar.id)
    if not await phd_file.sees_entry(session, principal, scholar, copy.annexure, copy.record_id):
        raise forbidden()


async def require_upload(session: AsyncSession, principal: Principal, copy_id: uuid.UUID) -> None:
    """The scan goes on once, by whoever made the place for it."""
    copy, _ = await _live(session, copy_id)
    if copy.uploaded_by != principal.user_id:
        raise forbidden()
    if await _file(session, copy.id, ready_only=False) is not None:
        raise ApiError(
            409, "already_uploaded", "This copy has its scan. Upload a new copy instead."
        )


async def approve(session: AsyncSession, principal: Principal, copy_id: uuid.UUID) -> None:
    copy, scholar = await _live(session, copy_id)
    await scope.get_scholar_or_403(session, principal, scholar.id)
    if not await scope.can_record(session, principal, scholar):
        raise forbidden()
    if await _file(session, copy.id) is None:
        raise ApiError(409, "upload_incomplete", "The scan has not finished uploading.")
    if copy.approved_at is None:
        await update(
            session,
            principal,
            copy,
            {"approved_by": principal.user_id, "approved_at": datetime.now(UTC)},
        )


async def remove(session: AsyncSession, principal: Principal, copy_id: uuid.UUID) -> None:
    """Whoever uploaded it, until it is approved; the keepers at any time."""
    copy, scholar = await _live(session, copy_id)
    await scope.get_scholar_or_403(session, principal, scholar.id)
    own = copy.uploaded_by == principal.user_id and copy.approved_at is None
    if not own and not await scope.can_record(session, principal, scholar):
        raise forbidden()
    await soft_delete(session, principal, copy)
    if f := await _file(session, copy.id, ready_only=False):
        await soft_delete(session, principal, f)


async def _file(
    session: AsyncSession, copy_id: uuid.UUID, ready_only: bool = True
) -> FileRow | None:
    stmt = select(FileRow).where(
        FileRow.table_name == "signed_copies",
        FileRow.record_id == copy_id,
        FileRow.deleted_at.is_(None),
    )
    if ready_only:
        stmt = stmt.where(FileRow.status == "ready")
    return await session.scalar(stmt)


async def in_use(session: AsyncSession, scholar_id: uuid.UUID) -> dict[uuid.UUID, dict[str, Any]]:
    """The copy in use for each record of the scholar's file: the newest with its scan in place.
    Approved ones carry a short-lived link to the scan, for the export service to merge it."""
    rows = await session.execute(
        select(SignedCopy, FileRow, User.full_name)
        .join(
            FileRow,
            (FileRow.table_name == "signed_copies")
            & (FileRow.record_id == SignedCopy.id)
            & (FileRow.status == "ready")
            & FileRow.deleted_at.is_(None),
        )
        .join(User, User.id == SignedCopy.uploaded_by)
        .where(SignedCopy.scholar_id == scholar_id, SignedCopy.deleted_at.is_(None))
        .order_by(SignedCopy.created_at.desc())
    )
    out: dict[uuid.UUID, dict[str, Any]] = {}
    for copy, f, uploader in rows:
        out.setdefault(
            copy.record_id,
            {
                "id": copy.id,
                "file_id": f.id,
                "file_name": f.file_name,
                "content_type": f.content_type,
                "uploaded_by": uploader,
                "uploaded_at": copy.created_at,
                "approved_at": copy.approved_at,
                "scan_url": storage.presign_get(f.storage_key, f.file_name)
                if copy.approved_at
                else None,
            },
        )
    return out


def attach(annexures: list[dict[str, Any]], copies: dict[uuid.UUID, dict[str, Any]]) -> None:
    """Each entry of the built file gains its copy in use; an approved one marks it signed."""
    for a in annexures:
        for e in a["entries"]:
            copy = copies.get(e["record"]) if e["record"] else None
            e["signed_copy"] = copy
            if copy and copy["approved_at"]:
                e["signed"] = True
