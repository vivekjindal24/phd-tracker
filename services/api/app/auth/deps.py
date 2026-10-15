"""Request-level auth dependencies: JWT → User → Actor (user + entity link).

Actor resolves the caller's scholar/supervisor row once per request; every scoping
and permission check in the app consumes it.
"""

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..errors import ApiError
from ..models import Scholar, Supervisor, User

bearer = HTTPBearer(auto_error=False)


@dataclass
class Actor:
	user: User
	role: str
	scholar_id: uuid.UUID | None = None
	supervisor_id: uuid.UUID | None = None


def _parse_token(creds: HTTPAuthorizationCredentials | None) -> dict:
	from ..config import settings  # deferred: tests may set JWT_SECRET before first auth call

	if creds is None:
		raise ApiError(401, "unauthenticated", "Missing bearer token")
	if not settings.jwt_secret:
		raise ApiError(500, "misconfigured", "JWT_SECRET is not set — auth disabled")
	try:
		return jwt.decode(creds.credentials, settings.jwt_secret, algorithms=["HS256"])
	except jwt.ExpiredSignatureError:
		raise ApiError(401, "invalid_token", "Access token has expired") from None
	except jwt.InvalidTokenError:
		raise ApiError(401, "invalid_token", "Access token is invalid") from None


async def get_current_user(
	request: Request,
	creds: HTTPAuthorizationCredentials | None = Depends(bearer),
	db: AsyncSession = Depends(get_db),
) -> User:
	payload = _parse_token(creds)
	user = await db.get(User, uuid.UUID(payload["sub"]))
	if user is None or user.deleted_at is not None:
		raise ApiError(401, "invalid_token", "Access token is invalid")
	return user


async def get_actor(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Actor:
	actor = Actor(user=user, role=user.role)
	if user.role == "scholar":
		actor.scholar_id = await db.scalar(
			select(Scholar.id).where(Scholar.user_id == user.id, Scholar.deleted_at.is_(None))
		)
	elif user.role == "supervisor":
		actor.supervisor_id = await db.scalar(
			select(Supervisor.id).where(Supervisor.user_id == user.id, Supervisor.deleted_at.is_(None))
		)
	return actor