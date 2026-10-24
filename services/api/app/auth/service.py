"""Passwords, access JWTs, rotating refresh tokens, login throttling, set-password links
(SECURITY.md §1)."""

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud import update as audited_update
from app.errors import ApiError
from app.models import LoginAttempt, PasswordToken, RefreshToken, User
from app.notify import email_configured, send_email

log = logging.getLogger("anveshan.auth")

# RFC 9106 second recommended (low-memory) profile: t=3, m=64 MiB, p=4.
_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)
JWT_ALGORITHM = "HS256"
THROTTLE_MAX_FAILURES = 5
THROTTLE_WINDOW = timedelta(minutes=15)
PASSWORD_LINK_TTL = timedelta(hours=72)

_INVALID = ApiError(401, "invalid_credentials", "Email or password is incorrect.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if password_hash is None:
        return False  # invited / SSO-only account: no password set yet
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise jwt.InvalidTokenError("not an access token")
        return uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise ApiError(401, "invalid_token", "Your session has expired. Please log in.") from exc


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def _issue_refresh(session: AsyncSession, user_id: uuid.UUID) -> str:
    raw = secrets.token_urlsafe(48)
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=_hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        )
    )
    return raw


async def _check_throttle(session: AsyncSession, email: str) -> None:
    since = datetime.now(UTC) - THROTTLE_WINDOW
    failures = await session.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(LoginAttempt.email == email.lower(), LoginAttempt.at >= since)
    )
    if (failures or 0) >= THROTTLE_MAX_FAILURES:
        raise ApiError(429, "too_many_attempts", "Too many attempts, try again in 15 minutes.")


async def issue_tokens(session: AsyncSession, user_id: uuid.UUID) -> tuple[str, str]:
    """A fresh access + refresh pair for a user who has just proven who they are."""
    refresh = await _issue_refresh(session, user_id)
    await session.commit()
    return create_access_token(user_id), refresh


async def login(session: AsyncSession, email: str, password: str) -> tuple[str, str]:
    await _check_throttle(session, email)
    user = await session.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None or not user.is_active or not verify_password(user.password_hash, password):
        session.add(LoginAttempt(email=email.lower()))
        await session.commit()
        raise _INVALID
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return await issue_tokens(session, user.id)


async def rotate_refresh(session: AsyncSession, raw: str) -> tuple[str, str]:
    """Single-use: the presented token is revoked and a new pair issued."""
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == _hash_token(raw)).with_for_update()
    )
    now = datetime.now(UTC)
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise ApiError(401, "invalid_token", "Your session has expired. Please log in.")
    user = await session.get(User, row.user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise ApiError(401, "invalid_token", "Your session has expired. Please log in.")
    row.revoked_at = now
    refresh = await _issue_refresh(session, user.id)
    await session.commit()
    return create_access_token(user.id), refresh


async def revoke_refresh(session: AsyncSession, raw: str) -> None:
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == _hash_token(raw))
    )
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        await session.commit()


async def revoke_all_refresh(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Log out every device, e.g. after a password change."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


# --- set-password links (invite / forgot password) ---------------------------------------

_LINK_INVALID = ApiError(
    422, "invalid_link", "This link is invalid or has expired. Ask for a new one."
)
EMAIL_NOT_CONFIGURED = ApiError(
    422,
    "email_not_configured",
    "Email is not configured on this server, so no link can be sent.",
)


async def issue_password_link(session: AsyncSession, user_id: uuid.UUID, purpose: str) -> str:
    """A new single-use link; any older unused link for the same user stops working."""
    now = datetime.now(UTC)
    await session.execute(
        update(PasswordToken)
        .where(PasswordToken.user_id == user_id, PasswordToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw = secrets.token_urlsafe(32)
    session.add(
        PasswordToken(
            user_id=user_id,
            token_hash=_hash_token(raw),
            purpose=purpose,
            expires_at=now + PASSWORD_LINK_TTL,
        )
    )
    return raw


async def email_password_link(user: User, raw: str, purpose: str) -> None:
    link = f"{settings.app_base_url}/set-password?token={raw}"
    if purpose == "invite":
        subject = "Set your password"
        lead = "An account has been created for you on Anveshan, your university's research system."
    else:
        subject = "Reset your password"
        lead = "Someone (hopefully you) asked to reset your Anveshan password."
    body = "\n".join(
        [
            f"Dear {user.full_name},",
            "",
            lead,
            "Choose a password here (the link works once, for 72 hours):",
            link,
            "",
            "If you did not expect this email, you can ignore it.",
        ]
    )
    await send_email(user.email, subject, body)


async def forgot_password(session: AsyncSession, email: str) -> None:
    """Same answer whether or not the account exists; shares the login throttle."""
    if not email_configured():
        raise EMAIL_NOT_CONFIGURED
    await _check_throttle(session, email)
    session.add(LoginAttempt(email=email.lower()))
    user = await session.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    raw = None
    if user is not None and user.is_active:
        raw = await issue_password_link(session, user.id, "reset")
    await session.commit()
    if user is None or raw is None:
        return
    try:
        await email_password_link(user, raw, "reset")
    except Exception:
        # Not shown to the caller (it would reveal that the account exists): logged loudly.
        log.exception("password reset email to user %s failed", user.id)


async def set_password_with_link(session: AsyncSession, raw: str, password: str) -> uuid.UUID:
    row = await session.scalar(
        select(PasswordToken).where(PasswordToken.token_hash == _hash_token(raw)).with_for_update()
    )
    now = datetime.now(UTC)
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise _LINK_INVALID
    user = await session.get(User, row.user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise _LINK_INVALID
    row.used_at = now
    await audited_update(session, None, user, {"password_hash": hash_password(password)})
    await revoke_all_refresh(session, user.id)
    return user.id
