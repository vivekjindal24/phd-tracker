"""A scholar's grievance (owner, 2026-11-23; UGC Redressal of Grievances of Students
Regulations, 2023). The scholar files it; the grievance cell decides within 15 working days;
the scholar accepts, or appeals within 15 days to the Ombudsperson (or, where the university
has chosen so, the Vice Chancellor), who decides within 30 days.

Who reads one: the scholar who filed it, the grievance cell and the Vice Chancellor; whoever
decides appeals, once it is appealed. A cell member who supervises the scholar never sees it.
Nobody else: not the supervisor, heads, admins, the Research Office, nor the root admin. The
case's `status` changes only here."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, false, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app import dates
from app.auth.principal import Principal
from app.crud import insert, update
from app.enums import LOCAL_TZ
from app.errors import ApiError, forbidden
from app.models import Faculty, Grievance, RoleAssignment, Scholar, Settings, User
from app.notify import notify

CELL_WORKING_DAYS = 15  # UGC 2023: the committee decides within 15 working days
APPEAL_WINDOW_DAYS = 15  # the scholar appeals within 15 days of the decision
APPEAL_DAYS = 30  # the Ombudsperson decides within 30 days
REMIND_DAYS_BEFORE = 3
APPEALS_LABEL = {"ombudsperson": "the Ombudsperson", "vice_chancellor": "the Vice Chancellor"}
ICC_NOTE = "A complaint of sexual harassment goes to the Internal Complaints Committee, not here."


def today() -> date:
    return datetime.now(LOCAL_TZ).date()


def working_days_after(start: date, days: int) -> date:
    """`days` weekdays after `start`.
    ponytail: Saturdays and Sundays only; add the university's holiday list if deadlines bite."""
    d = start
    while days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days -= 1
    return d


async def appeals_to(session: AsyncSession) -> str:
    row = await session.get(Settings, 1)
    assert row is not None, "settings row is seeded by migration 0001"
    return row.grievance_appeals_to


def _supervised_by(faculty_id: uuid.UUID) -> Any:
    return select(Scholar.id).where(
        or_(Scholar.supervisor_id == faculty_id, Scholar.co_supervisor_id == faculty_id)
    )


def visible(principal: Principal, appellate: str) -> ColumnElement[bool]:
    clauses: list[ColumnElement[bool]] = []
    if principal.scholar_id:
        clauses.append(Grievance.scholar_id == principal.scholar_id)
    if "grievance_cell" in principal.office_roles:
        clauses.append(
            Grievance.scholar_id.notin_(_supervised_by(principal.faculty_id))
            if principal.faculty_id
            else true()
        )
    if "vice_chancellor" in principal.office_roles:
        clauses.append(true())
    if appellate in principal.office_roles:
        clauses.append(Grievance.appealed_at.is_not(None))
    return or_(*clauses, false())


async def get_or_403(session: AsyncSession, principal: Principal, gid: uuid.UUID) -> Grievance:
    row = await session.scalar(
        select(Grievance).where(
            Grievance.id == gid,
            Grievance.deleted_at.is_(None),
            visible(principal, await appeals_to(session)),
        )
    )
    if row is None:
        raise forbidden()
    return row


def _appeal_closes(g: Grievance) -> date | None:
    if g.decided_at is None:
        return None
    return g.decided_at.astimezone(LOCAL_TZ).date() + timedelta(days=APPEAL_WINDOW_DAYS)


def allowed(principal: Principal, g: Grievance, appellate: str) -> dict[str, bool]:
    """What the caller may do with it now; every action re-checks through `_require`."""
    own = principal.scholar_id == g.scholar_id
    cell = "grievance_cell" in principal.office_roles and not own
    appeal_open = (_appeal_closes(g) or today()) >= today()
    return {
        "decide": cell and g.status == "open",
        "withdraw": own and g.status == "open",
        "accept": own and g.status == "decided",
        "appeal": own and g.status == "decided" and appeal_open,
        "decide_appeal": appellate in principal.office_roles and g.status == "appealed",
        "attach": ((own or cell) and g.status == "open")
        or (appellate in principal.office_roles and g.status == "appealed"),
    }


async def _require(session: AsyncSession, principal: Principal, g: Grievance, action: str) -> str:
    appellate = await appeals_to(session)
    if not allowed(principal, g, appellate)[action]:
        raise ApiError(
            409, "grievance_state", "This step is not open to you while the grievance is here."
        )
    return appellate


async def require_attach(session: AsyncSession, principal: Principal, gid: uuid.UUID) -> None:
    await _require(session, principal, await get_or_403(session, principal, gid), "attach")


async def _holders(session: AsyncSession, role: str, scholar_id: uuid.UUID) -> list[uuid.UUID]:
    """Who holds `role`, less anyone who supervises the scholar."""
    supervisors = (
        select(Faculty.user_id)
        .join(
            Scholar,
            or_(Scholar.supervisor_id == Faculty.id, Scholar.co_supervisor_id == Faculty.id),
        )
        .where(Scholar.id == scholar_id)
    )
    rows = await session.scalars(
        select(RoleAssignment.user_id).where(
            RoleAssignment.role == role,
            RoleAssignment.deleted_at.is_(None),
            RoleAssignment.user_id.notin_(supervisors),
        )
    )
    return list(rows)


async def _scholar_user(session: AsyncSession, g: Grievance) -> uuid.UUID:
    uid = await session.scalar(select(Scholar.user_id).where(Scholar.id == g.scholar_id))
    assert uid is not None
    return uid


def _tell(session: AsyncSession, users: list[uuid.UUID], title: str, g: Grievance) -> None:
    """Never the grievance's words in a notification or email: only that there is one."""
    notify(
        session, users, "system", title, "Open it in Anveshan to read it.", f"/grievances/{g.id}"
    )


async def file(session: AsyncSession, principal: Principal, data: dict[str, Any]) -> Grievance:
    if principal.scholar_id is None:
        raise ApiError(403, "forbidden", "Scholars file their own grievances.")
    g = await insert(
        session,
        principal,
        Grievance(
            scholar_id=principal.scholar_id,
            status="open",
            due_on=working_days_after(today(), CELL_WORKING_DAYS),
            **data,
        ),
    )
    _tell(
        session, await _holders(session, "grievance_cell", g.scholar_id), "A grievance was filed", g
    )
    return g


async def decide(session: AsyncSession, principal: Principal, g: Grievance, text: str) -> None:
    await _require(session, principal, g, "decide")
    now = datetime.now(UTC)
    changes = {
        "status": "decided",
        "decision": text,
        "decided_at": now,
        "decided_by": principal.user_id,
    }
    await update(session, principal, g, changes)
    _tell(session, [await _scholar_user(session, g)], "Your grievance has a decision", g)


async def withdraw(session: AsyncSession, principal: Principal, g: Grievance) -> None:
    await _require(session, principal, g, "withdraw")
    await update(session, principal, g, {"status": "withdrawn", "closed_at": datetime.now(UTC)})
    _tell(
        session,
        await _holders(session, "grievance_cell", g.scholar_id),
        "A grievance was withdrawn",
        g,
    )


async def accept(session: AsyncSession, principal: Principal, g: Grievance) -> None:
    await _require(session, principal, g, "accept")
    await update(session, principal, g, {"status": "closed", "closed_at": datetime.now(UTC)})


async def appeal(session: AsyncSession, principal: Principal, g: Grievance, reason: str) -> None:
    appellate = await _require(session, principal, g, "appeal")
    changes = {
        "status": "appealed",
        "appeal_reason": reason,
        "appealed_at": datetime.now(UTC),
        "due_on": today() + timedelta(days=APPEAL_DAYS),
    }
    await update(session, principal, g, changes)
    _tell(session, await _holders(session, appellate, g.scholar_id), "A grievance was appealed", g)


async def decide_appeal(
    session: AsyncSession, principal: Principal, g: Grievance, text: str
) -> None:
    await _require(session, principal, g, "decide_appeal")
    now = datetime.now(UTC)
    changes = {
        "status": "appeal_decided",
        "appeal_decision": text,
        "appeal_decided_at": now,
        "appeal_decided_by": principal.user_id,
        "closed_at": now,
    }
    await update(session, principal, g, changes)
    users = [
        await _scholar_user(session, g),
        *await _holders(session, "grievance_cell", g.scholar_id),
    ]
    _tell(session, users, "A grievance appeal was decided", g)


async def view(session: AsyncSession, principal: Principal, g: Grievance) -> dict[str, Any]:
    appellate = await appeals_to(session)
    ids = [i for i in (g.decided_by, g.appeal_decided_by) if i]
    names = dict(
        (await session.execute(select(User.id, User.full_name).where(User.id.in_(ids)))).all()
    )
    scholar = await session.scalar(
        select(User.full_name)
        .join(Scholar, Scholar.user_id == User.id)
        .where(Scholar.id == g.scholar_id)
    )
    return {
        "id": g.id,
        "scholar": {"id": g.scholar_id, "name": scholar},
        "category": g.category,
        "subject": g.subject,
        "description": g.description,
        "status": g.status,
        "filed_at": g.created_at,
        "due_on": g.due_on if g.status in ("open", "appealed") else None,
        "decision": g.decision,
        "decided_at": g.decided_at,
        "decided_by": names.get(g.decided_by),
        "appeal_closes_on": _appeal_closes(g) if g.status == "decided" else None,
        "appeal_reason": g.appeal_reason,
        "appealed_at": g.appealed_at,
        "appeal_decision": g.appeal_decision,
        "appeal_decided_at": g.appeal_decided_at,
        "appeal_decided_by": names.get(g.appeal_decided_by),
        "appeals_to": APPEALS_LABEL[appellate],
        "can": allowed(principal, g, appellate),
    }


async def daily(session: AsyncSession, day: date) -> dict[str, int]:
    """Reminders before each deadline, a notice the day after a missed one (to the Vice
    Chancellor too), and decisions nobody appealed in time closed."""
    appellate = await appeals_to(session)
    vcs = list(
        await session.scalars(
            select(RoleAssignment.user_id).where(
                RoleAssignment.role == "vice_chancellor", RoleAssignment.deleted_at.is_(None)
            )
        )
    )
    counts = {"grievance_reminders": 0, "grievances_overdue": 0, "grievances_closed": 0}
    rows = await session.scalars(
        select(Grievance).where(
            Grievance.deleted_at.is_(None),
            Grievance.status.in_(("open", "appealed", "decided")),
        )
    )
    for g in rows:
        if g.status == "decided":
            closes = _appeal_closes(g)
            if closes is not None and closes < day:
                await update(session, None, g, {"status": "closed", "closed_at": datetime.now(UTC)})
                counts["grievances_closed"] += 1
            continue
        role = "grievance_cell" if g.status == "open" else appellate
        holders = await _holders(session, role, g.scholar_id)
        if g.due_on - timedelta(days=REMIND_DAYS_BEFORE) == day:
            _tell(session, holders, f"A grievance is due on {dates.day(g.due_on)}", g)
            counts["grievance_reminders"] += 1
        elif g.due_on + timedelta(days=1) == day:
            _tell(session, [*holders, *vcs], "A grievance is past its deadline", g)
            counts["grievances_overdue"] += 1
    return counts
