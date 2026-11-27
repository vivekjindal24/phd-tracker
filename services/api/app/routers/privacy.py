"""Personal data (DPDP Act 2023, privacy.py): the privacy notice, open to anyone; each person's
summary and requests; and the privacy officer's list of requests."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import privacy
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session
from app.schemas import (
    DataRequestAnswerIn,
    DataRequestIn,
    DataRequestOut,
    PrivacyNoticeOut,
)

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.get("", response_model=PrivacyNoticeOut)
async def get_notice(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Public, like the branding: the notice is read before signing in too."""
    return await privacy.notice_view(session)


@router.post("/seen", status_code=204)
async def notice_seen(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    await privacy.mark_seen(session, principal)
    await session.commit()


@router.get("/my-data")
async def my_data(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    return JSONResponse(
        jsonable_encoder(await privacy.summary(session, principal)),
        headers={"Content-Disposition": 'attachment; filename="my-data-anveshan.json"'},
    )


@router.get("/requests/mine", response_model=list[DataRequestOut])
async def my_requests(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    return await privacy.mine(session, principal)


@router.post("/requests", response_model=DataRequestOut, status_code=201)
async def ask(
    body: DataRequestIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    out = await privacy.ask(session, principal, body.kind, body.details)
    await session.commit()
    return out


@router.get("/requests", response_model=list[DataRequestOut])
async def every_request(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    return await privacy.all_requests(session, principal)


@router.post("/requests/{request_id}/answer", response_model=DataRequestOut)
async def answer(
    request_id: uuid.UUID,
    body: DataRequestAnswerIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    out = await privacy.answer(session, principal, request_id, body.reply)
    await session.commit()
    return out
