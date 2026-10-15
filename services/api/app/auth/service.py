"""Email+password auth: 30-min HS256 access JWT + DB-backed rotating refresh tokens.

Refresh tokens are stored as sha256 hex — the raw value exists only in the response
and the client. Rotation is single-use: presenting a token revokes it and issues a
new one; a replayed (already-revoked) token is rejected loudly.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..errors import ApiError
from ..models import RefreshToken, User

ACCESS_TTL = timedelta(minutes=30)
REFRESH_TTL = timedelta(days=30)

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
	return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
	try:
		_hasher.verify(password_hash, password)
	except VerifyMismatchError:
		return False
	return True


def create_access_token(user: User) -> str:
	payload = {
		"sub": str(user.id),
		"role": user.role,
		"exp": datetime.now(UTC) + ACCESS_TTL,
	}
	if not settings.jwt_secret:
		# config.py loads lazily at import; this is the loud login-time gate promised there.
		raise ApiError(500, "misconfigured", "JWT_SECRET is not set — login disabled")
	return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _hash_token(raw: str) -> str:
	return hashlib.sha256(raw.encode()).hexdigest()


async def issue_refresh(db: AsyncSession, user_id) -> str:
	raw = secrets.token_urlsafe(48)
	db.add(
		RefreshToken(
			user_id=user_id,
			token_hash=_hash_token(raw),
			expires_at=datetime.now(UTC) + REFRESH_TTL,
		)
	)
	return raw


async def _load_live_token(db: AsyncSession, raw: str) -> RefreshToken:
	token = await db.scalar(
		select(RefreshToken).where(RefreshToken.token_hash == _hash_token(raw))
	)
	if token is None or token.revoked_at is not None:
		raise ApiError(401, "invalid_refresh_token", "Refresh token is invalid or already used")
	if token.expires_at < datetime.now(UTC):
		raise ApiError(401, "invalid_refresh_token", "Refresh token has expired")
	return token


async def rotate_refresh(db: AsyncSession, raw: str) -> tuple[User, str]:
	"""Single-use rotation: revoke the presented token, mint a fresh one."""
	token = await _load_live_token(db, raw)
	token.revoked_at = datetime.now(UTC)
	user = await db.get(User, token.user_id)
	if user is None or user.deleted_at is not None:
		raise ApiError(401, "invalid_refresh_token", "Refresh token is invalid or already used")
	return user, await issue_refresh(db, user.id)


async def revoke_refresh(db: AsyncSession, raw: str) -> None:
	await db.execute(
		update(RefreshToken)
		.where(RefreshToken.token_hash == _hash_token(raw), RefreshToken.revoked_at.is_(None))
		.values(revoked_at=datetime.now(UTC))
	)


async def login(db: AsyncSession, email: str, password: str) -> tuple[User, str, str]:
	user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
	if user is None or not verify_password(password, user.password_hash):
		# Same error for unknown email and wrong password — no user enumeration.
		raise ApiError(401, "invalid_credentials", "Email or password is incorrect")
	return user, create_access_token(user), await issue_refresh(db, user.id)