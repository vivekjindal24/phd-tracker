"""Bulk import (PRD F16, UX Flow 5): download a template, upload a filled file for a dry run,
upload it again to import. The file is the raw request body — no multipart needed."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app import bulk_import, spreadsheet
from app.auth.principal import Principal
from app.db import get_session
from app.errors import ApiError
from app.rbac import require_perm
from app.schemas.administration import ImportReport

router = APIRouter(prefix="/import", tags=["import"])

ImportKind = Literal["faculty", "scholars", "history"]
MAX_IMPORT_BYTES = 5 * 1024 * 1024
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _read_capped(request: Request) -> bytes:
    """The upload, refused as soon as it passes the cap (never buffered past it)."""
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_IMPORT_BYTES:
            raise ApiError(413, "file_too_large", "Import files can be at most 5 MB.")
        chunks.append(chunk)
    if size == 0:
        raise ApiError(422, "empty_file", "Choose a filled-in template to upload.")
    return b"".join(chunks)


@router.get("/{kind}/template")
async def template(
    kind: ImportKind,
    _: Principal = Depends(require_perm("bulk_import", "create")),
) -> Response:
    content = spreadsheet.template(bulk_import.KINDS[kind], kind.title())
    return Response(
        content,
        media_type=XLSX,
        headers={"Content-Disposition": f'attachment; filename="anveshan-{kind}-template.xlsx"'},
    )


@router.post("/{kind}", response_model=ImportReport)
async def run_import(
    kind: ImportKind,
    request: Request,
    dry_run: bool = True,
    send_invitations: bool = False,
    principal: Principal = Depends(require_perm("bulk_import", "create")),
    session: AsyncSession = Depends(get_session),
) -> bulk_import.Report:
    rows = spreadsheet.read_rows(await _read_capped(request), bulk_import.KINDS[kind])
    return await bulk_import.run(
        session,
        principal,
        kind,
        rows,
        dry_run=dry_run,
        send_invitations=send_invitations and kind != "history",
    )
