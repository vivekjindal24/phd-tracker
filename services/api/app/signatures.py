"""Specimen signatures (PRD F17b): each person's real signature, stamped on what they sign.

Two ways in. The person uploads it themself, and it waits until someone else confirms it. Or
they sign on paper at their department and a keeper uploads it for them, which is the
confirmation. Keepers are an admin over the person's unit, the Research Office and the root
admin (scope.signature_keeper_predicate). Nobody confirms their own."""

import base64
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.errors import ApiError, forbidden
from app.models import Faculty, OrgUnit, RoleAssignment, Scholar, Signature, User
from app.models.base import Ltree
from app.notify import notify


async def current(session: AsyncSession, user_id: uuid.UUID) -> Signature | None:
    return await session.scalar(
        select(Signature).where(Signature.user_id == user_id, Signature.deleted_at.is_(None))
    )


def data_url(sig: Signature) -> str:
    return f"data:{sig.content_type};base64,{base64.b64encode(sig.content).decode()}"


def view(sig: Signature | None) -> dict[str, Any] | None:
    if sig is None:
        return None
    return {
        "image": data_url(sig),
        "uploaded_at": sig.created_at,
        "uploaded_by_self": sig.uploaded_by == sig.user_id,
        "confirmed_at": sig.confirmed_at,
    }


async def require_keeper(session: AsyncSession, principal: Principal, user_id: uuid.UUID) -> None:
    found = await session.scalar(
        select(User.id).where(
            User.id == user_id,
            User.deleted_at.is_(None),
            scope.signature_keeper_predicate(principal),
        )
    )
    if found is None:
        raise forbidden()


async def require_self_or_keeper(
    session: AsyncSession, principal: Principal, user_id: uuid.UUID
) -> None:
    if principal.user_id != user_id:
        await require_keeper(session, principal, user_id)


async def replace(
    session: AsyncSession,
    principal: Principal,
    user_id: uuid.UUID,
    content: bytes,
    content_type: str,
) -> None:
    """The caller is the person (waits for a keeper, who is told) or a keeper, already checked,
    handing in the paper signature (confirmed now)."""
    await remove(session, principal, user_id)
    keeper = principal.user_id != user_id
    if not keeper:
        notify(
            session,
            await keepers(session, user_id),
            "system",
            f"{principal.full_name}'s signature waits for your confirmation",
            "Compare it with their paper signature, then confirm it.",
            "/people/signatures",
        )
    await insert(
        session,
        principal,
        Signature(
            user_id=user_id,
            content=content,
            content_type=content_type,
            uploaded_by=principal.user_id,
            confirmed_by=principal.user_id if keeper else None,
            confirmed_at=datetime.now(UTC) if keeper else None,
        ),
    )


async def confirm(session: AsyncSession, principal: Principal, user_id: uuid.UUID) -> None:
    if principal.user_id == user_id:
        raise ApiError(403, "own_signature", "Someone else must confirm your signature.")
    await require_keeper(session, principal, user_id)
    sig = await current(session, user_id)
    if sig is None:
        raise ApiError(404, "not_found", "There is no signature to confirm.")
    if sig.confirmed_at is None:
        await update(
            session,
            principal,
            sig,
            {"confirmed_by": principal.user_id, "confirmed_at": datetime.now(UTC)},
        )


async def remove(session: AsyncSession, principal: Principal, user_id: uuid.UUID) -> None:
    if sig := await current(session, user_id):
        await soft_delete(session, principal, sig)


async def pending(session: AsyncSession, principal: Principal) -> list[dict[str, Any]]:
    """Signatures waiting for the caller to confirm, oldest first; never the caller's own."""
    rows = await session.execute(
        select(Signature, User)
        .join(User, User.id == Signature.user_id)
        .where(
            Signature.deleted_at.is_(None),
            Signature.confirmed_at.is_(None),
            User.deleted_at.is_(None),
            User.id != principal.user_id,
            scope.signature_keeper_predicate(principal),
        )
        .order_by(Signature.created_at)
    )
    return [
        {"user_id": u.id, "full_name": u.full_name, "email": u.email, "signature": view(s)}
        for s, u in rows
    ]


async def keepers(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Who should confirm this person's signature: the admins of the nearest unit at or above
    theirs (as a scholar or faculty member), else the Research Office."""
    units = (
        select(Scholar.unit_id)
        .where(Scholar.user_id == user_id)
        .union(select(Faculty.unit_id).where(Faculty.user_id == user_id))
    )
    own = await session.scalars(select(OrgUnit.path).where(OrgUnit.id.in_(units)))
    paths = list(own)
    rows = []
    if paths:
        rows = (
            await session.execute(
                select(RoleAssignment.user_id, func.nlevel(OrgUnit.path))
                .join(OrgUnit, OrgUnit.id == RoleAssignment.unit_id)
                .where(
                    RoleAssignment.deleted_at.is_(None),
                    RoleAssignment.role == "admin",
                    RoleAssignment.user_id != user_id,
                    or_(*[OrgUnit.path.op("@>")(cast(literal(p), Ltree)) for p in paths]),
                )
            )
        ).all()
    if rows:
        nearest = max(level for _, level in rows)
        return [uid for uid, level in rows if level == nearest]
    return list(
        await session.scalars(
            select(RoleAssignment.user_id).where(
                RoleAssignment.role == "research_office",
                RoleAssignment.deleted_at.is_(None),
                RoleAssignment.user_id != user_id,
            )
        )
    )
