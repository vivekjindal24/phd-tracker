"""Signing an approval (PRD F17b), while the university requires it (`settings.require_signing`).

An approve or send-back is a signature, not a click: the signer needs a confirmed specimen
signature (signatures.py) and a fresh code. The code comes from their authenticator app when
they have one set up (the same key as two-factor login, a code works once); otherwise one is
emailed to them for this action on this item. Wrong authenticator codes count toward a throttle
of their own; an emailed code dies after five wrong tries."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import signatures, workflow
from app.auth import totp
from app.auth.principal import Principal
from app.auth.service import check_throttle, count_failure
from app.errors import ApiError
from app.models import Settings, SigningCode, User
from app.notify import email_configured, send_email
from app.workflow import ItemContext

CODE_TTL = timedelta(minutes=10)
MAX_TRIES = 5
RESEND_GAP = timedelta(seconds=60)
ACTION_TEXT = {"approve": "approve", "send_back": "send back"}

INVALID = ApiError(403, "invalid_code", "That code is not right. Check it and try again.")


async def required(session: AsyncSession) -> bool:
    return bool(await session.scalar(select(Settings.require_signing).where(Settings.id == 1)))


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _throttle_key(user: User) -> str:
    """Wrong authenticator codes when signing: throttled apart from logins, so a guesser at an
    open session cannot also lock the person out of logging in."""
    return f"signing:{user.email.lower()}"


async def _user(session: AsyncSession, principal: Principal) -> User:
    user = await session.get(User, principal.user_id, with_for_update=True)
    assert user is not None
    return user


async def send_code(
    session: AsyncSession, principal: Principal, ctx: ItemContext, action: str
) -> None:
    if not await required(session):
        raise ApiError(422, "signing_not_required", "Signing is not switched on.")
    if not await workflow.can_act(session, principal, ctx):
        raise workflow.violation("You cannot act on this item at its current step.")
    user = await _user(session, principal)
    if user.totp_enabled_at is not None:
        raise ApiError(422, "use_authenticator", "Use the code from your authenticator app.")
    if not email_configured():
        raise ApiError(
            422,
            "signing_needs_authenticator",
            "Email is not set up on this server, so signing needs an authenticator app. "
            "Ask your admin.",
        )
    now = datetime.now(UTC)
    last = await session.scalar(
        select(func.max(SigningCode.created_at)).where(SigningCode.user_id == user.id)
    )
    if last is not None and now - last < RESEND_GAP:
        raise ApiError(429, "code_recently_sent", "A code was just sent. Wait a minute.")
    open_codes = (
        SigningCode.user_id == user.id,
        SigningCode.item_type == ctx.item_type,
        SigningCode.item_id == ctx.item.id,
        SigningCode.action == action,
        SigningCode.used_at.is_(None),
    )
    await session.execute(update(SigningCode).where(*open_codes).values(used_at=now))
    code = f"{secrets.randbelow(10**6):06d}"
    session.add(
        SigningCode(
            user_id=user.id,
            item_type=ctx.item_type,
            item_id=ctx.item.id,
            action=action,
            code_hash=_hash(code),
            expires_at=now + CODE_TTL,
        )
    )
    await session.commit()
    body = "\n".join(
        [
            f"Dear {user.full_name},",
            "",
            f"Your code to {ACTION_TEXT[action]} {ctx.label} of {ctx.scholar.roll_number} is:",
            "",
            f"    {code}",
            "",
            "It works once, for 10 minutes, and only for this action.",
            "If you did not ask for it, someone may be using your open session: log out "
            "everywhere and change your password.",
        ]
    )
    await send_email(user.email, f"Signing code {code}", body)


async def verify(
    session: AsyncSession, principal: Principal, ctx: ItemContext, action: str, code: str | None
) -> None:
    """Raises unless the caller may sign this action now. A no-op while signing is off."""
    if not await required(session):
        return
    sig = await signatures.current(session, principal.user_id)
    if sig is None or sig.confirmed_at is None:
        raise ApiError(
            422,
            "signature_required",
            "Signing needs your signature on file and confirmed. Add it under My account.",
        )
    user = await _user(session, principal)
    method = "authenticator" if user.totp_enabled_at is not None else "email"
    if not code:
        raise ApiError(
            422, "signing_code_required", "Enter a code to sign this.", {"method": method}
        )
    now = datetime.now(UTC)
    if method == "authenticator":
        await check_throttle(session, _throttle_key(user))
        assert user.totp_secret is not None
        step = totp.matching_step(user.totp_secret, code, now.timestamp(), user.totp_last_step)
        if not step:
            raise await count_failure(session, _throttle_key(user), INVALID)
        user.totp_last_step = step
        return
    row = await session.scalar(
        select(SigningCode)
        .where(
            SigningCode.user_id == user.id,
            SigningCode.item_type == ctx.item_type,
            SigningCode.item_id == ctx.item.id,
            SigningCode.action == action,
            SigningCode.used_at.is_(None),
            SigningCode.expires_at > now,
            SigningCode.attempts < MAX_TRIES,
        )
        .order_by(SigningCode.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if row is None:
        raise ApiError(
            422, "signing_code_expired", "That code has expired or was used. Send a new one."
        )
    if not hmac.compare_digest(row.code_hash, _hash(code)):
        row.attempts += 1
        await session.commit()  # the wrong try counts even though the action fails
        raise INVALID
    row.used_at = now
