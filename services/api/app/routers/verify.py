"""Public certificate verification (PRD M3): the one route with personal data and no login.
The token is 256 random bits printed on the certificate; the answer is the schema's short list."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import certificate
from app.db import get_session
from app.schemas.research import CertificateVerification

router = APIRouter(prefix="/verify", tags=["verify"])


@router.get("/{token}", response_model=CertificateVerification)
async def verify(token: str, session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    return await certificate.public_view(session, token)
