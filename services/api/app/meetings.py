"""Meeting rules (PRD F7, SECURITY.md §3): both parties see everything; anyone else in scope
sees the full record only if the MAIN supervisor shared it with their group — otherwise just
that a meeting happened. Redaction is computed here, never in the client."""

import uuid
from datetime import date, timedelta

from app.auth.principal import Principal
from app.errors import ApiError, forbidden
from app.models import Meeting, Scholar

FUTURE_SLACK = timedelta(days=1)  # time-zone slack; meetings are logged after they happen


def is_party(principal: Principal, scholar: Scholar) -> bool:
    if principal.scholar_id == scholar.id:
        return True
    fid = principal.faculty_id
    if fid is None:
        return False
    return fid == scholar.supervisor_id or (
        principal.co_supervision != "off" and fid == scholar.co_supervisor_id
    )


def can_share(principal: Principal, scholar: Scholar) -> bool:
    return principal.faculty_id is not None and principal.faculty_id == scholar.supervisor_id


def sees_full(principal: Principal, meeting: Meeting, scholar: Scholar, unit_path: str) -> bool:
    if is_party(principal, scholar):
        return True
    shared = set(meeting.shared_with)
    return (
        ("unit_heads" in shared and principal.covers("unit_head", unit_path))
        or ("admins" in shared and principal.covers("admin", unit_path))
        or ("research_office" in shared and "research_office" in principal.office_roles)
    )


def resolve_supervisor(
    principal: Principal, scholar: Scholar, requested: uuid.UUID | None
) -> uuid.UUID:
    """The faculty side of the meeting: the scholar's supervisor, or the co-supervisor when
    co-supervision is on (and they are the one logging it or were named)."""
    allowed = {scholar.supervisor_id}
    if principal.co_supervision != "off":
        allowed.add(scholar.co_supervisor_id)
    allowed.discard(None)
    if not allowed:
        raise ApiError(
            422,
            "no_supervisor",
            "This scholar has no supervisor yet; a meeting needs both parties.",
        )
    if requested is None:
        requested = (
            principal.faculty_id if principal.faculty_id in allowed else scholar.supervisor_id
        )
    if requested not in allowed:
        raise ApiError(
            422,
            "not_a_supervisor_of_scholar",
            "Meetings are logged with the scholar's supervisor or co-supervisor.",
        )
    assert requested is not None
    return requested


def check_dates(meeting_date: date, next_date: date | None) -> None:
    if meeting_date > date.today() + FUTURE_SLACK:
        raise ApiError(422, "meeting_in_future", "Log a meeting after it has taken place.")
    if next_date is not None and next_date < meeting_date:
        raise ApiError(
            422, "next_before_meeting", "The next meeting must be on or after this meeting's date."
        )


def require_party(principal: Principal, scholar: Scholar) -> None:
    if not is_party(principal, scholar):
        raise forbidden()
