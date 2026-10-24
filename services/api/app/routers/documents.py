"""Drafts & chapters with versions (PRD M3). Only the scholar and their supervisor(s) see them;
the supervisor gives feedback as comments. Versions are append-only."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import records, scope
from app.auth.principal import Principal
from app.crud import insert, update
from app.db import get_session
from app.errors import ApiError, forbidden
from app.models import Document, DocumentVersion, FileRow, Scholar, User
from app.modules import require_module
from app.rbac import require_perm
from app.schemas import DocumentIn, DocumentOut, DocumentUpdate, VersionIn

router = APIRouter(
    prefix="/documents", tags=["documents"], dependencies=[Depends(require_module("documents"))]
)


def _query(principal: Principal) -> Select:
    return (
        select(Document, Scholar.id, User.full_name)
        .join(Scholar, Scholar.id == Document.scholar_id)
        .join(User, User.id == Scholar.user_id)
        .where(
            Document.deleted_at.is_(None),
            Scholar.deleted_at.is_(None),
            scope.scholar_predicate(principal, "documents"),
        )
    )


async def _out(session: AsyncSession, principal: Principal, row) -> dict[str, Any]:
    doc, sid, name = row
    versions = await session.execute(
        select(DocumentVersion, FileRow)
        .join(FileRow, FileRow.id == DocumentVersion.file_id)
        .where(DocumentVersion.document_id == doc.id, DocumentVersion.deleted_at.is_(None))
        .order_by(DocumentVersion.version_no.desc())
    )
    return {
        "id": doc.id,
        "scholar": {"id": sid, "name": name},
        "title": doc.title,
        "doc_kind": doc.doc_kind,
        "updated_at": doc.updated_at,
        "can_edit": sid == principal.scholar_id,
        "versions": [
            {
                "id": v.id,
                "version_no": v.version_no,
                "note": v.note,
                "file_id": f.id,
                "file_name": f.file_name,
                "size_bytes": f.size_bytes,
                "created_at": v.created_at,
            }
            for v, f in versions
        ],
    }


async def _one(session: AsyncSession, principal: Principal, document_id: uuid.UUID):
    row = (await session.execute(_query(principal).where(Document.id == document_id))).first()
    if row is None:
        raise forbidden()
    return await _out(session, principal, row)


async def _own(session: AsyncSession, principal: Principal, document_id: uuid.UUID) -> Document:
    doc, _ = await records.document_or_403(session, principal, document_id)
    if doc.scholar_id != principal.scholar_id:
        raise forbidden()
    return doc


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    scholar_id: uuid.UUID | None = None,
    principal: Principal = Depends(require_perm("documents", "read")),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = _query(principal)
    if scholar_id:
        stmt = stmt.where(Document.scholar_id == scholar_id)
    rows = await session.execute(stmt.order_by(Document.updated_at.desc()).limit(500))
    return [await _out(session, principal, r) for r in rows]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(require_perm("documents", "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _one(session, principal, document_id)


@router.post("", response_model=DocumentOut, status_code=201)
async def create_document(
    body: DocumentIn,
    principal: Principal = Depends(require_perm("documents", "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if principal.scholar_id is None:
        raise ApiError(403, "forbidden", "Scholars keep their own documents.")
    doc = await insert(
        session, principal, Document(scholar_id=principal.scholar_id, **body.model_dump())
    )
    await session.commit()
    return await _one(session, principal, doc.id)


@router.patch("/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: uuid.UUID,
    body: DocumentUpdate,
    principal: Principal = Depends(require_perm("documents", "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    doc = await _own(session, principal, document_id)
    await update(session, principal, doc, body.model_dump(exclude_unset=True))
    await session.commit()
    return await _one(session, principal, document_id)


@router.post("/{document_id}/versions", response_model=DocumentOut, status_code=201)
async def add_version(
    document_id: uuid.UUID,
    body: VersionIn,
    principal: Principal = Depends(require_perm("documents", "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """The file is uploaded to the document first (/files), then becomes the next version."""
    doc = await _own(session, principal, document_id)
    f = await session.get(FileRow, body.file_id)
    if (
        f is None
        or f.deleted_at is not None
        or f.table_name != "documents"
        or f.record_id != doc.id
        or f.status != "ready"
    ):
        raise ApiError(422, "file_not_ready", "Upload the file to this document first.")
    latest = await session.scalar(
        select(func.max(DocumentVersion.version_no)).where(DocumentVersion.document_id == doc.id)
    )
    await insert(
        session,
        principal,
        DocumentVersion(
            document_id=doc.id, version_no=(latest or 0) + 1, file_id=f.id, note=body.note
        ),
    )
    await update(session, principal, doc, {"updated_at": func.now()})
    await session.commit()
    return await _one(session, principal, document_id)
