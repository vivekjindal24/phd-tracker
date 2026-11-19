"""Signed copies of the PhD file's forms (PRD F17b, signed_copies.py). The scan itself goes up
as a file on the copy (POST /files/uploads, table `signed_copies`)."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app import signed_copies
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session
from app.enums import PhdAnnexure

router = APIRouter(tags=["scholars"])


class SignedCopyIn(BaseModel):
    annexure: PhdAnnexure
    record_id: uuid.UUID


class SignedCopyOut(BaseModel):
    id: uuid.UUID


@router.post("/scholars/{scholar_id}/signed-copies", response_model=SignedCopyOut, status_code=201)
async def create_signed_copy(
    scholar_id: uuid.UUID,
    body: SignedCopyIn,
    principal: Principal = Depends(current_principal),  # signed_copies.py decides
    session: AsyncSession = Depends(get_session),
) -> SignedCopyOut:
    copy = await signed_copies.create(session, principal, scholar_id, body.annexure, body.record_id)
    await session.commit()
    return SignedCopyOut(id=copy.id)


@router.post("/signed-copies/{copy_id}/approve", status_code=204)
async def approve_signed_copy(
    copy_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    await signed_copies.approve(session, principal, copy_id)
    await session.commit()


@router.delete("/signed-copies/{copy_id}", status_code=204)
async def delete_signed_copy(
    copy_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    await signed_copies.remove(session, principal, copy_id)
    await session.commit()
