"""The provisional PhD certificate (PRD M3): the Research Office issues it after a passed viva,
serial <university code>/PHD/<year>/<n>; a public page verifies it by a random token; revoking
keeps the row, and the serial, for good."""

import secrets
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import thesis
from app.auth.principal import Principal
from app.config import settings
from app.crud import insert, update
from app.errors import ApiError
from app.models import (
    OrgUnit,
    ProvisionalCertificate,
    Scholar,
    ThesisSubmission,
    User,
    Viva,
)
from app.notify import notify
from app.workflow import ItemContext

NOT_FOUND = ApiError(404, "not_found", "We could not find this certificate.")


async def _viva_date(session: AsyncSession, thesis_id: uuid.UUID) -> date | None:
    return await session.scalar(
        select(func.max(Viva.held_on)).where(
            Viva.thesis_id == thesis_id, Viva.outcome == "pass", Viva.deleted_at.is_(None)
        )
    )


async def _live(session: AsyncSession, thesis_id: uuid.UUID) -> ProvisionalCertificate | None:
    return await session.scalar(
        select(ProvisionalCertificate).where(
            ProvisionalCertificate.thesis_id == thesis_id,
            ProvisionalCertificate.revoked_at.is_(None),
            ProvisionalCertificate.deleted_at.is_(None),
        )
    )


async def issue(session: AsyncSession, principal: Principal, ctx: ItemContext) -> None:
    if await _viva_date(session, ctx.item.id) is None:
        raise ApiError(422, "viva_not_passed", "A certificate needs a passed viva.")
    if await _live(session, ctx.item.id):
        raise ApiError(409, "certificate_exists", "A valid certificate already exists.")
    if await thesis.approved_title(session, ctx.scholar.id) is None:
        raise thesis.TITLE_NOT_APPROVED
    await thesis.sync_title(session, principal, ctx.scholar.id)
    today = date.today()
    # ponytail: two offices issuing in the same instant collide on uq_certificate_serial and
    # retry by hand; a per-year counter row removes that if it ever happens.
    number = 1 + (
        await session.scalar(
            select(func.coalesce(func.max(ProvisionalCertificate.number), 0)).where(
                ProvisionalCertificate.year == today.year
            )
        )
    )
    code = await session.scalar(select(OrgUnit.code).where(OrgUnit.parent_id.is_(None)))
    await insert(
        session,
        principal,
        ProvisionalCertificate(
            thesis_id=ctx.item.id,
            year=today.year,
            number=number,
            serial=f"{code}/PHD/{today.year}/{number}",
            verify_token=secrets.token_urlsafe(32),
            issued_on=today,
        ),
    )
    notify(
        session,
        [ctx.scholar.user_id],
        "system",
        "Your provisional certificate is ready",
        link=ctx.link,
    )


async def revoke(
    session: AsyncSession, principal: Principal, ctx: ItemContext, reason: str
) -> None:
    live = await _live(session, ctx.item.id)
    if live is None:
        raise ApiError(422, "no_live_certificate", "There is no valid certificate to revoke.")
    await update(
        session,
        principal,
        live,
        {"revoked_at": datetime.now(UTC), "revoked_reason": reason},
    )
    notify(
        session,
        [ctx.scholar.user_id],
        "system",
        "Your provisional certificate was revoked",
        reason,
        ctx.link,
    )


async def public_view(session: AsyncSession, token: str) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ProvisionalCertificate, ThesisSubmission.title, User.full_name, OrgUnit.name)
            .join(ThesisSubmission, ThesisSubmission.id == ProvisionalCertificate.thesis_id)
            .join(Scholar, Scholar.id == ThesisSubmission.scholar_id)
            .join(User, User.id == Scholar.user_id)
            .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
            .where(
                ProvisionalCertificate.verify_token == token,
                ProvisionalCertificate.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        raise NOT_FOUND
    cert, title, name, unit = row
    return {
        "name": name,
        "thesis_title": title,
        "unit": unit,
        "viva_date": await _viva_date(session, cert.thesis_id),
        "issued_on": cert.issued_on,
        "status": "revoked" if cert.revoked_at else "valid",
    }


async def export_view(
    session: AsyncSession, principal: Principal, certificate_id: uuid.UUID
) -> dict[str, Any]:
    cert = await session.get(ProvisionalCertificate, certificate_id)
    if cert is None or cert.deleted_at is not None:
        raise NOT_FOUND
    ctx = await thesis.load_thesis(session, principal, cert.thesis_id)  # the reader check
    if cert.revoked_at is not None:
        raise ApiError(409, "certificate_revoked", "This certificate was revoked.")
    wording = settings.certificate
    return {
        "unit": await session.scalar(select(OrgUnit.name).where(OrgUnit.id == ctx.scholar.unit_id)),
        "serial": cert.serial,
        "scholar": await session.scalar(
            select(User.full_name).where(User.id == ctx.scholar.user_id)
        ),
        "roll_number": ctx.scholar.roll_number,
        "degree": wording.degree,
        "opening": wording.opening,
        "title_lead": wording.title_lead,
        "body": wording.body,
        "signatories": wording.signatories,
        "thesis_title": ctx.item.title,
        "viva_date": await _viva_date(session, cert.thesis_id),
        "issued_on": cert.issued_on,
        "verify_url": f"{settings.app_base_url}/verify/{cert.verify_token}",
    }
