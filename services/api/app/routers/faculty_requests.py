"""Requests to faculty outside the caller's view (SECURITY.md §3). Who may act depends on the
seminar or scholar, so app/faculty_requests.py decides per request, not the matrix."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import faculty_requests
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session
from app.schemas import FacultyRequestIn, FacultyRequestList, FacultyRequestOut

router = APIRouter(prefix="/faculty-requests", tags=["directory"])


@router.get("", response_model=FacultyRequestList)
async def list_requests(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, list[dict[str, Any]]]:
    return await faculty_requests.listing(session, principal)


@router.post("", response_model=FacultyRequestOut, status_code=201)
async def create_request(
    body: FacultyRequestIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await faculty_requests.create(session, principal, body)


@router.post("/{request_id}/accept", response_model=FacultyRequestOut)
async def accept_request(
    request_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await faculty_requests.accept(session, principal, request_id)


@router.post("/{request_id}/decline", response_model=FacultyRequestOut)
async def decline_request(
    request_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await faculty_requests.decline(session, principal, request_id)


@router.post("/{request_id}/cancel", response_model=FacultyRequestOut)
async def cancel_request(
    request_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await faculty_requests.cancel(session, principal, request_id)
