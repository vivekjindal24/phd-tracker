from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal, load_principal
from app.auth.service import decode_access_token
from app.db import get_session
from app.errors import ApiError
from app.models import User

_bearer = HTTPBearer(auto_error=False)


async def current_principal(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> Principal:
    if creds is None:
        raise ApiError(401, "unauthorized", "Please log in.")
    user = await session.get(User, decode_access_token(creds.credentials))
    if user is None or user.deleted_at is not None or not user.is_active:
        raise ApiError(401, "invalid_token", "Your session has expired. Please log in.")
    return await load_principal(session, user)


def require_root_admin(principal: Principal = Depends(current_principal)) -> Principal:
    if not principal.is_root_admin:
        raise ApiError(403, "forbidden", "Only a university administrator can do this.")
    return principal
