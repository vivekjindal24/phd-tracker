"""Signed copies (PRD F17b): the scans of the papers signed on paper, put in the PhD file after
the entry they belong to. Each entry holds its own papers (phd_file.py: a seminar's notification,
report and attendance sheet, …); a copy is keyed by the annexure, the record behind the entry and
the paper's kind.

Who uploads: an admin over the scholar's unit, the Research Office, or the scholar's supervisor
(co-supervisor too where co-supervision is on). Who approves: the admin or the Research Office
(scope.can_record); their own uploads count as approved at once. A supervisor's upload waits, and
the keepers are told. The papers naming the examiners (enums.EXAMINER_DOCUMENTS) are handled by
the admin, the Research Office and the Exam Office alone, and seen only by them (phd_file.py).
Everyone who uploads, approves or removes is in the audit log (crud.py). Reading a copy follows
the entry it stands for: whoever sees that entry in the file sees it."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import phd_file, scope, signatures, storage
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.enums import DOCUMENT_KINDS, EXAMINER_DOCUMENTS
from app.errors import ApiError, forbidden
from app.models import FileRow, Scholar, SignedCopy, User
from app.notify import notify


async def rights(session: AsyncSession, principal: Principal, scholar: Scholar) -> dict[str, bool]:
    """What the caller may do with this scholar's signed copies; examiner papers apart."""
    keeper = await scope.can_record(session, principal, scholar)
    return {
        "upload": keeper or scope.guides(principal, scholar),
        "approve": keeper,
        "examiner": keeper or "exam_office" in principal.office_roles,  # uploads and approves
    }


def _may(rights: dict[str, bool], kind: str, act: str) -> bool:
    return rights["examiner"] if kind in EXAMINER_DOCUMENTS else rights[act]


async def create(
    session: AsyncSession,
    principal: Principal,
    scholar_id: uuid.UUID,
    annexure: str,
    record_id: uuid.UUID,
    kind: str,
) -> SignedCopy:
    """A place for the scan; the browser then uploads it as a file on this row (files.py)."""
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id)
    can = await rights(session, principal, scholar)
    if not _may(can, kind, "upload"):
        raise forbidden()
    entry = await phd_file.find_entry(session, principal, scholar, annexure, record_id)
    if entry is None:
        raise ApiError(404, "not_found", "That entry is not in this scholar's file.")
    if kind not in entry["papers"]:
        raise ApiError(422, "wrong_paper", f"{entry['heading']} holds no {DOCUMENT_KINDS[kind]}.")
    keeper = _may(can, kind, "approve")
    now = datetime.now(UTC)
    copy = await insert(
        session,
        principal,
        SignedCopy(
            scholar_id=scholar.id,
            annexure=annexure,
            record_id=record_id,
            kind=kind,
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


async def require_read(
    session: AsyncSession, principal: Principal, copy_id: uuid.UUID
) -> tuple[SignedCopy, Scholar]:
    copy, scholar = await _live(session, copy_id)
    await scope.get_scholar_or_403(session, principal, scholar.id)
    found = await phd_file.find_entry(session, principal, scholar, copy.annexure, copy.record_id)
    if found is None:
        raise forbidden()
    return copy, scholar


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
    copy, scholar = await require_read(session, principal, copy_id)
    if not _may(await rights(session, principal, scholar), copy.kind, "approve"):
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
    copy, scholar = await require_read(session, principal, copy_id)
    own = copy.uploaded_by == principal.user_id and copy.approved_at is None
    if not own and not _may(await rights(session, principal, scholar), copy.kind, "approve"):
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


Key = tuple[str, uuid.UUID, str]  # annexure, record, kind


async def in_use(session: AsyncSession, scholar_id: uuid.UUID) -> dict[Key, dict[str, Any]]:
    """The copy in use for each paper of the scholar's file: the newest with its scan in place.
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
    out: dict[Key, dict[str, Any]] = {}
    for copy, f, uploader in rows:
        out.setdefault(
            (copy.annexure, copy.record_id, copy.kind),
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


def attach(
    annexures: list[dict[str, Any]], copies: dict[Key, dict[str, Any]], can: dict[str, bool]
) -> None:
    """Each entry's papers, in order, with the copy in use and what the caller may do with it.
    An approved copy marks its entry signed."""
    for a in annexures:
        for e in a["entries"]:
            e["papers"] = [
                {
                    "kind": kind,
                    "label": DOCUMENT_KINDS[kind],
                    "copy": copies.get((a["key"], e["record"], kind)),
                    "may_upload": _may(can, kind, "upload"),
                    "may_approve": _may(can, kind, "approve"),
                }
                for kind in e["papers"]
            ]
            if any(p["copy"] and p["copy"]["approved_at"] for p in e["papers"]):
                e["signed"] = True
