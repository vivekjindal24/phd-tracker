"""Viva arrangements (PRD M3): the Exam Office proposes when and where the viva is held and who
sits on the board (Forms X and XI); the arrangement goes up its approval chain (the Vice
Chancellor by default), then the external examiners are emailed and the viva itself is
recorded against it (Form XII, `vivas`).

- One open arrangement per thesis: a new one only once the last has its viva recorded.
- External examiners' names follow the examiner rule (thesis.py): only the offices that see
  examiners read them, never the scholar's own guide, until a viva is recorded."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import items, thesis
from app.auth.principal import Principal
from app.branding import public_view
from app.enums import LOCAL_TZ
from app.errors import ApiError
from app.models import (
    ExaminerReport,
    Faculty,
    OrgUnit,
    ThesisSubmission,
    User,
    Viva,
    VivaArrangement,
    VivaBoardMember,
)
from app.notify import email_configured, notify, send_email
from app.workflow import ItemContext, is_guide, violation

ROLE_ORDER = ("chairperson", "external_examiner", "member")


def when(at: datetime) -> str:
    return f"{at.astimezone(LOCAL_TZ):%d %b %Y, %I:%M %p} IST"


async def held(session: AsyncSession, arrangement_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(Viva.id).where(Viva.arrangement_id == arrangement_id, Viva.deleted_at.is_(None))
    )
    return found is not None


async def open_arrangement(session: AsyncSession, thesis_id: uuid.UUID) -> VivaArrangement | None:
    """The thesis's arrangement whose viva is not recorded yet, if any."""
    rows = await session.scalars(
        select(VivaArrangement).where(
            VivaArrangement.thesis_id == thesis_id, VivaArrangement.deleted_at.is_(None)
        )
    )
    for a in rows:
        if not await held(session, a.id):
            return a
    return None


def sees_names(principal: Principal, ctx: ItemContext, viva_held: bool) -> bool:
    return viva_held or (items.sees_examiners(principal) and not is_guide(principal, ctx))


async def members(session: AsyncSession, arrangement_id: uuid.UUID) -> list[VivaBoardMember]:
    return list(
        await session.scalars(
            select(VivaBoardMember).where(
                VivaBoardMember.arrangement_id == arrangement_id,
                VivaBoardMember.deleted_at.is_(None),
            )
        )
    )


async def board(session: AsyncSession, principal: Principal, ctx: ItemContext) -> dict[str, Any]:
    """The board as this viewer may see it: the supervisor, then each member by role."""
    a: VivaArrangement = ctx.item  # type: ignore[assignment]
    names = sees_names(principal, ctx, await held(session, a.id))
    rows = await session.execute(
        select(VivaBoardMember, User.full_name, OrgUnit.name)
        .outerjoin(Faculty, Faculty.id == VivaBoardMember.faculty_id)
        .outerjoin(User, User.id == Faculty.user_id)
        .outerjoin(OrgUnit, OrgUnit.id == Faculty.unit_id)
        .where(VivaBoardMember.arrangement_id == a.id, VivaBoardMember.deleted_at.is_(None))
    )
    out = []
    for m, faculty_name, unit in rows:
        hidden = m.role == "external_examiner" and not names
        out.append(
            {
                "id": m.id,
                "role": m.role,
                "name": None if hidden else (m.name or faculty_name),
                "institution": None if hidden else (m.institution or unit),
                "email": m.email if names else None,
                "external": m.faculty_id is None,
            }
        )
    out.sort(key=lambda m: (ROLE_ORDER.index(m["role"]), m["name"] or ""))
    supervisor = await session.scalar(
        select(User.full_name)
        .join(Faculty, Faculty.user_id == User.id)
        .where(Faculty.id == ctx.scholar.supervisor_id)
    )
    office = "exam_office" in principal.office_roles and not is_guide(principal, ctx)
    return {
        "supervisor": supervisor,
        "members": out,
        "names_hidden": not names,
        "can_edit": a.state in ("draft", "sent_back") and office,
        "can_invite": a.state == "approved" and office and not await held(session, a.id),
        "email_configured": email_configured(),
    }


async def check_ready(session: AsyncSession, _: Principal, ctx: ItemContext) -> None:
    """Before the Exam Office submits: a future date, a place, a chairperson, an external
    examiner, released reports, and no final outcome already."""
    a: VivaArrangement = ctx.item  # type: ignore[assignment]
    if a.scheduled_at <= datetime.now(UTC):
        raise violation("Set a date and time for the viva that is still to come.")
    if not (a.venue or a.online_link):
        raise violation("Give the venue or the online link for the viva.")
    roles = {m.role for m in await members(session, a.id)}
    if "chairperson" not in roles or "external_examiner" not in roles:
        raise violation("Name the board's chairperson and at least one external examiner.")
    block = thesis.viva_block(
        await thesis.rows(session, ExaminerReport, a.thesis_id),
        await thesis.rows(session, Viva, a.thesis_id),
    )
    if block:
        raise ApiError(422, *block)


async def invite(session: AsyncSession, ctx: ItemContext) -> int:
    """Email every external examiner the approved arrangement. Returns how many were sent;
    raises on the first failure, leaving `invited_at` unset so it can be sent again."""
    a: VivaArrangement = ctx.item  # type: ignore[assignment]
    if not email_configured():
        raise ApiError(503, "email_not_configured", "Email is not configured on this server.")
    examiners = [m for m in await members(session, a.id) if m.role == "external_examiner"]
    university = (await public_view(session))["university"]
    scholar = await session.scalar(select(User.full_name).where(User.id == ctx.scholar.user_id))
    thesis_title = await session.scalar(
        select(ThesisSubmission.title).where(ThesisSubmission.id == a.thesis_id)
    )
    place = a.venue or ""
    if a.online_link:
        place = f"{place} (online: {a.online_link})" if place else f"Online: {a.online_link}"
    for m in examiners:
        body = "\n".join(
            [
                f"Dear {m.name},",
                "",
                f"{university} invites you to conduct the PhD viva-voce examination of",
                f"{scholar}, as the external examiner.",
                "",
                f"Thesis: {thesis_title}",
                f"Date and time: {when(a.scheduled_at)}",
                f"Venue: {place}",
                "",
                "The Examination Office will write to you with travel and other details.",
            ]
        )
        try:
            await send_email(str(m.email), "Invitation to conduct a PhD viva-voce", body)
        except Exception as exc:
            raise ApiError(502, "email_failed", f"The invitation could not be sent: {exc}") from exc
    return len(examiners)


async def announce(session: AsyncSession, _: Principal, ctx: ItemContext) -> None:
    """On approval: the supervisor and the faculty on the board hear when and where (the
    scholar is told by the engine). Nothing names the external examiners."""
    a: VivaArrangement = ctx.item  # type: ignore[assignment]
    faculty_ids = [m.faculty_id for m in await members(session, a.id) if m.faculty_id]
    faculty_ids.append(ctx.scholar.supervisor_id)
    users = await session.scalars(
        select(Faculty.user_id).where(Faculty.id.in_([f for f in faculty_ids if f]))
    )
    place = a.venue or "online"
    notify(
        session,
        users,
        "system",
        "A viva you sit on is approved",
        f"{when(a.scheduled_at)}, {place}",
        ctx.link,
    )
