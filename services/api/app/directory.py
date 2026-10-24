"""Directory rules (PRD F6): supervisor assignment under UGC caps, co-supervision setting,
scholar/faculty edits by admins over their unit."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope
from app.auth.principal import Principal
from app.crud import insert, update
from app.enums import UGC_CAP
from app.errors import ApiError, forbidden
from app.models import Faculty, Scholar, Settings, User
from app.notify import notify


async def create_person(
    session: AsyncSession,
    principal: Principal,
    *,
    email: str,
    full_name: str,
    password_hash: str | None,
    faculty: Faculty | None = None,
    scholar: Scholar | None = None,
) -> User:
    """One way to add a person — the Add-person form and bulk import both come here (PRD F6,
    F16). `faculty` / `scholar` are unsaved profiles; their unit decides which admin may."""
    profile = faculty or scholar
    if profile is None:
        # Bare accounts (office staff) belong to no unit: only the root admin creates them.
        if not principal.is_root_admin:
            raise forbidden()
    else:
        scope.require_admin_over(principal, await scope.unit_path(session, profile.unit_id))
    user = await insert(
        session, principal, User(email=email, full_name=full_name, password_hash=password_hash)
    )
    if profile is not None:
        profile.user_id = user.id
        await insert(session, principal, profile)
    return user


async def require_admin_over_scholar(
    session: AsyncSession, principal: Principal, scholar: Scholar
) -> None:
    scope.require_admin_over(principal, await scope.unit_path(session, scholar.unit_id))


async def _live_faculty(session: AsyncSession, faculty_id: uuid.UUID, lock: bool) -> Faculty:
    stmt = select(Faculty).where(Faculty.id == faculty_id, Faculty.deleted_at.is_(None))
    if lock:
        stmt = stmt.with_for_update()  # serialises concurrent assignments to one supervisor
    faculty = await session.scalar(stmt)
    if faculty is None:
        raise ApiError(422, "faculty_not_found", "This faculty member does not exist.")
    return faculty


async def supervisor_load(session: AsyncSession, faculty_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Scholar)
        .where(Scholar.supervisor_id == faculty_id, Scholar.deleted_at.is_(None))
    )
    return count or 0


async def assign_supervisor(
    session: AsyncSession,
    principal: Principal,
    scholar: Scholar,
    faculty_id: uuid.UUID | None,
    *,
    announce: bool = True,  # bulk import loads history quietly: no "now your scholar" mail
) -> None:
    await require_admin_over_scholar(session, principal, scholar)
    if faculty_id == scholar.supervisor_id:
        return
    if faculty_id is None:
        await update(session, principal, scholar, {"supervisor_id": None})
        return
    faculty = await _live_faculty(session, faculty_id, lock=True)
    if not faculty.can_supervise:
        raise ApiError(422, "cannot_supervise", "This faculty member is not a supervisor.")
    if faculty_id == scholar.co_supervisor_id:
        raise ApiError(
            422,
            "already_co_supervisor",
            "This person is already the co-supervisor; remove that first.",
        )
    if await supervisor_load(session, faculty_id) >= faculty.max_scholars:
        raise ApiError(
            409,
            "supervisor_cap_exceeded",
            f"This supervisor already guides {faculty.max_scholars} scholars, "
            "the UGC limit for their designation.",
        )
    await update(session, principal, scholar, {"supervisor_id": faculty_id})
    if not announce:
        return
    scholar_name = await session.scalar(select(User.full_name).where(User.id == scholar.user_id))
    notify(
        session,
        [faculty.user_id],
        "system",
        f"{scholar_name} is now your scholar",
        link=f"/scholars/{scholar.id}",
    )
    notify(
        session,
        [scholar.user_id],
        "system",
        "Your supervisor has been assigned",
        link=f"/scholars/{scholar.id}",
    )


async def assign_co_supervisor(
    session: AsyncSession, principal: Principal, scholar: Scholar, faculty_id: uuid.UUID | None
) -> None:
    await require_admin_over_scholar(session, principal, scholar)
    mode = await session.scalar(select(Settings.co_supervision).where(Settings.id == 1))
    if mode == "off" and faculty_id is not None:
        raise ApiError(
            422, "co_supervision_off", "Co-supervision is switched off for this university."
        )
    if faculty_id is not None:
        await _live_faculty(session, faculty_id, lock=False)
        if faculty_id == scholar.supervisor_id:
            raise ApiError(
                422,
                "co_supervisor_same_as_supervisor",
                "The co-supervisor must be someone other than the supervisor.",
            )
    await update(session, principal, scholar, {"co_supervisor_id": faculty_id})


def validate_faculty_cap(designation: str, max_scholars: int) -> None:
    """Universities may set a LOWER cap than UGC's, never a higher one."""
    if max_scholars > UGC_CAP[designation]:
        raise ApiError(
            422,
            "cap_above_ugc",
            f"UGC allows at most {UGC_CAP[designation]} scholars for a {designation}.",
        )
