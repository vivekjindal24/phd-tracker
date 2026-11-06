from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal, load_principal
from app.auth.service import decode_access_token
from app.db import get_session
from app.errors import ApiError
from app.models import User

_bearer = HTTPBearer(auto_error=False)


async def any_principal(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> Principal:
    if creds is None:
        raise ApiError(401, "unauthorized", "Please log in.")
    user = await session.get(User, decode_access_token(creds.credentials))
    if user is None or user.deleted_at is not None or not user.is_active:
        raise ApiError(401, "invalid_token", "Your session has expired. Please log in.")
    return await load_principal(session, user)


def current_principal(principal: Principal = Depends(any_principal)) -> Principal:
    """The default guard. A thesis reviewer is refused here, so every route is closed to them
    unless it asks for any_principal or current_reviewer by name (PRD M3)."""
    if principal.is_reviewer:
        raise ApiError(403, "reviewers_only_review", "This account can only open its reviews.")
    return principal


def current_reviewer(principal: Principal = Depends(any_principal)) -> Principal:
    if not principal.is_reviewer:
        raise ApiError(403, "forbidden", "This page is for invited thesis reviewers.")
    return principal


def require_root_admin(principal: Principal = Depends(current_principal)) -> Principal:
    if not principal.is_root_admin:
        raise ApiError(403, "forbidden", "Only a university administrator can do this.")
    return principal
