import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import meetings, scope
from app.auth.principal import Principal
from app.crud import insert, update
from app.db import get_session
from app.errors import ApiError, forbidden
from app.models import Faculty, Meeting, OrgUnit, Scholar, User
from app.notify import notify
from app.rbac import require_perm
from app.schemas import MeetingIn, MeetingOut, MeetingUpdate, Ref

router = APIRouter(prefix="/meetings", tags=["meetings"])

ScholarUser = aliased(User)
SupUser = aliased(User)


def _query(principal: Principal) -> Select:
    return (
        select(Meeting, Scholar, OrgUnit.path, ScholarUser.full_name, SupUser.full_name)
        .join(Scholar, Scholar.id == Meeting.scholar_id)
        .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
        .join(ScholarUser, ScholarUser.id == Scholar.user_id)
        .join(Faculty, Faculty.id == Meeting.supervisor_id)
        .join(SupUser, SupUser.id == Faculty.user_id)
        .where(
            Meeting.deleted_at.is_(None),
            Scholar.deleted_at.is_(None),
            scope.scholar_predicate(principal, "meetings"),
        )
    )


def _out(principal: Principal, row) -> MeetingOut:
    m, scholar, path, scholar_name, sup_name = row
    full = meetings.sees_full(principal, m, scholar, path)
    party = meetings.is_party(principal, scholar)
    return MeetingOut(
        id=m.id,
        scholar=Ref(id=scholar.id, name=scholar_name),
        supervisor=Ref(id=m.supervisor_id, name=sup_name),
        meeting_date=m.meeting_date,
        redacted=not full,
        agenda=m.agenda if full else None,
        minutes=m.minutes if full else None,
        action_items=m.action_items if full else None,
        next_meeting_date=m.next_meeting_date if full else None,
        shared_with=list(m.shared_with),
        can_edit=party,
        can_share=meetings.can_share(principal, scholar),
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


async def _one(session: AsyncSession, principal: Principal, meeting_id: uuid.UUID) -> MeetingOut:
    row = (await session.execute(_query(principal).where(Meeting.id == meeting_id))).first()
    if row is None:
        raise forbidden()
    return _out(principal, row)


@router.get("", response_model=list[MeetingOut])
async def list_meetings(
    scholar_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_perm("meetings", "read")),
    session: AsyncSession = Depends(get_session),
) -> list[MeetingOut]:
    stmt = _query(principal)
    if scholar_id:
        stmt = stmt.where(Meeting.scholar_id == scholar_id)
    rows = await session.execute(
        stmt.order_by(Meeting.meeting_date.desc(), Meeting.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_out(principal, r) for r in rows]


@router.get("/{meeting_id}", response_model=MeetingOut)
async def get_meeting(
    meeting_id: uuid.UUID,
    principal: Principal = Depends(require_perm("meetings", "read")),
    session: AsyncSession = Depends(get_session),
) -> MeetingOut:
    return await _one(session, principal, meeting_id)


@router.post("", response_model=MeetingOut, status_code=201)
async def create_meeting(
    body: MeetingIn,
    principal: Principal = Depends(require_perm("meetings", "create")),
    session: AsyncSession = Depends(get_session),
) -> MeetingOut:
    scholar = await scope.get_scholar_or_403(session, principal, body.scholar_id, "meetings")
    meetings.require_party(principal, scholar)
    if body.shared_with and not meetings.can_share(principal, scholar):
        raise ApiError(
            422,
            "only_supervisor_shares",
            "Only the main supervisor decides who else may read the minutes.",
        )
    meetings.check_dates(body.meeting_date, body.next_meeting_date)
    supervisor_id = meetings.resolve_supervisor(principal, scholar, body.supervisor_id)
    meeting = await insert(
        session,
        principal,
        Meeting(
            scholar_id=scholar.id,
            supervisor_id=supervisor_id,
            meeting_date=body.meeting_date,
            agenda=body.agenda,
            minutes=body.minutes,
            action_items=body.action_items,
            next_meeting_date=body.next_meeting_date,
            shared_with=sorted(set(body.shared_with)),
            created_by=principal.user_id,
        ),
    )
    # Tell the other party.
    supervisor_user = await session.scalar(
        select(Faculty.user_id).where(Faculty.id == supervisor_id)
    )
    other = scholar.user_id if principal.user_id != scholar.user_id else supervisor_user
    if other and other != principal.user_id:
        notify(
            session,
            [other],
            "system",
            f"Meeting on {body.meeting_date:%d %b %Y} logged",
            body.agenda[:200],
            f"/meetings/{meeting.id}",
        )
    await session.commit()
    return await _one(session, principal, meeting.id)


@router.patch("/{meeting_id}", response_model=MeetingOut)
async def update_meeting(
    meeting_id: uuid.UUID,
    body: MeetingUpdate,
    principal: Principal = Depends(require_perm("meetings", "update")),
    session: AsyncSession = Depends(get_session),
) -> MeetingOut:
    meeting = await session.scalar(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.deleted_at.is_(None))
    )
    if meeting is None:
        raise forbidden()
    scholar = await scope.get_scholar_or_403(session, principal, meeting.scholar_id, "meetings")
    meetings.require_party(principal, scholar)
    changes = body.model_dump(exclude_unset=True)
    if "shared_with" in changes:
        if not meetings.can_share(principal, scholar):
            raise ApiError(
                422,
                "only_supervisor_shares",
                "Only the main supervisor decides who else may read the minutes.",
            )
        changes["shared_with"] = sorted(set(changes["shared_with"]))
    meetings.check_dates(
        changes.get("meeting_date", meeting.meeting_date),
        changes.get("next_meeting_date", meeting.next_meeting_date),
    )
    await update(session, principal, meeting, changes)
    await session.commit()
    return await _one(session, principal, meeting_id)
