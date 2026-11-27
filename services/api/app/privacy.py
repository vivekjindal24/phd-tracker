"""Personal data under the DPDP Act 2023: the university's privacy notice, which everyone reads
once and again whenever it changes; each person's summary of what Anveshan holds about them; and
their requests to correct or erase it, answered by the privacy officer the university names (the
root admins until one is named). The draft notice is Anveshan's starting point for the
university's lawyer, not legal advice."""

import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import branding, photos, signatures
from app.auth.principal import Principal
from app.config import settings as config
from app.crud import insert, update
from app.errors import ApiError, forbidden
from app.models import (
    DataRequest,
    Faculty,
    FileRow,
    OrgUnit,
    RoleAssignment,
    Scholar,
    Settings,
    User,
)
from app.notify import notify

DRAFT_NOTICE = """\
{university} uses Anveshan to run its research degree programme. This notice says what \
personal data it keeps about you, why, who sees it and what you can ask for.

What is kept. Your name, email address and, if you add one, your WhatsApp number; your roles. \
For scholars: roll number, department, supervisor, admission date, stage and research title; \
study mode, gender, category, whether you have a benchmark disability, minority community, \
nationality and father's name; your photo and specimen signature if you add them; and your \
research record — progress reports, seminars, meetings, publications, coursework, documents, \
thesis and examination. For faculty: designation, department and the scholars you supervise.

Why. To admit, supervise, examine and award research degrees under the University's \
ordinances and the UGC regulations, and to file the returns the law asks for (UGC, NIRF, \
AISHE, NAAC). Gender, category, disability, minority community and nationality are used only \
for those returns and for reservation rules.

Who sees it. People see only what their role needs: your supervisor your research record, \
your department's heads and admins your department's records, and the University's offices \
what their work needs. Gender, category, disability, minority community, nationality and \
father's name are not shown to supervisors or other faculty. Every change is recorded with \
who made it.

How long. Academic records are kept as long as the University must keep degree records. \
Other data is kept while you have an account and as the University's retention rules say.

Your rights. You may see a summary of what is kept about you and download it (My account → \
Your data), ask for a correction, ask for data to be erased where the law allows (records the \
University must keep cannot be erased), and complain to the University's privacy officer below. \
If you are not satisfied, you may complain to the Data Protection Board of India.
"""


async def officer(session: AsyncSession) -> User | None:
    officer_id = await session.scalar(select(Settings.privacy_officer_id))
    if officer_id is None:
        return None
    user = await session.get(User, officer_id)
    return user if user and user.is_active and user.deleted_at is None else None


async def handlers(session: AsyncSession) -> list[uuid.UUID]:
    """Who answers data requests: the privacy officer, or the root admins while none is named."""
    if named := await officer(session):
        return [named.id]
    return list(
        await session.scalars(
            select(RoleAssignment.user_id)
            .join(OrgUnit, OrgUnit.id == RoleAssignment.unit_id)
            .where(
                RoleAssignment.role == "admin",
                RoleAssignment.deleted_at.is_(None),
                OrgUnit.parent_id.is_(None),
            )
        )
    )


async def handles(session: AsyncSession, principal: Principal) -> bool:
    return principal.user_id in await handlers(session)


def _host(url: str) -> str:
    return urlparse(url).hostname or url


def processors() -> list[dict[str, str]]:
    """The outside services this installation sends personal data to, from its configuration."""
    out = [
        {
            "service": "File storage",
            "where": _host(config.s3.endpoint),
            "what": "Uploaded files and the scans of signed papers.",
        }
    ]
    if config.smtp:
        out.append(
            {
                "service": "Email",
                "where": config.smtp.host,
                "what": "Your name, email address and the notifications sent to you.",
            }
        )
    if config.whatsapp:
        out.append(
            {
                "service": "WhatsApp (Meta)",
                "where": "graph.facebook.com",
                "what": "Your WhatsApp number and the kind of each event, never names or content.",
            }
        )
    if config.ai:
        out.append(
            {
                "service": "AI writing assistant",
                "where": _host(config.ai.base_url),
                "what": "A supervisor's seminar remarks, to draft to-do points.",
            }
        )
    out.append(
        {
            "service": "Crossref and ORCID",
            "where": "api.crossref.org, pub.orcid.org",
            "what": "Only a DOI or ORCID iD you look up, never your name.",
        }
    )
    return out


async def notice_view(session: AsyncSession) -> dict[str, Any]:
    row = await session.get(Settings, 1)
    assert row is not None, "settings row is seeded by migration 0001"
    university = (await branding.public_view(session))["university"]
    named = await officer(session)
    return {
        "university": university,
        "text": row.privacy_notice or DRAFT_NOTICE.format(university=university),
        "is_draft": not row.privacy_notice,
        "officer": {"name": named.full_name, "email": named.email} if named else None,
        "changed_at": row.privacy_notice_changed_at,
        "processors": processors(),
    }


async def notice_due(session: AsyncSession, user: User) -> bool:
    if user.is_reviewer:  # an external examiner, reached only through their review link
        return False
    changed = await session.scalar(select(Settings.privacy_notice_changed_at))
    seen = user.privacy_notice_seen_at
    return seen is None or (changed is not None and seen < changed)


async def mark_seen(session: AsyncSession, principal: Principal) -> None:
    user = await session.get(User, principal.user_id)
    assert user is not None
    await update(session, principal, user, {"privacy_notice_seen_at": datetime.now(UTC)})


async def set_officer(
    session: AsyncSession, principal: Principal, user_id: uuid.UUID | None
) -> None:
    if user_id is not None:
        user = await session.get(User, user_id)
        if user is None or not user.is_active or user.deleted_at is not None or user.is_reviewer:
            raise ApiError(422, "not_a_user", "Choose an active member of the University.")
    row = await session.get(Settings, 1)
    assert row is not None
    await update(session, principal, row, {"privacy_officer_id": user_id})


# --- what Anveshan holds about one person ------------------------------------------------


async def _scholar_part(session: AsyncSession, scholar: Scholar) -> dict[str, Any]:
    unit = await session.scalar(select(OrgUnit.name).where(OrgUnit.id == scholar.unit_id))

    async def faculty_name(fid: uuid.UUID | None) -> str | None:
        if fid is None:
            return None
        return await session.scalar(
            select(User.full_name)
            .join(Faculty, Faculty.user_id == User.id)
            .where(Faculty.id == fid)
        )

    return {
        "roll_number": scholar.roll_number,
        "department": unit,
        "stage": scholar.stage,
        "admission_date": scholar.admission_date,
        "research_title": scholar.research_title,
        "study_mode": scholar.study_mode,
        "gender": scholar.gender,
        "category": scholar.category,
        "person_with_benchmark_disability": scholar.has_disability,
        "minority_community": scholar.minority,
        "nationality": scholar.nationality,
        "country": scholar.country,
        "father_name": scholar.father_name,
        "supervisor": await faculty_name(scholar.supervisor_id),
        "co_supervisor": await faculty_name(scholar.co_supervisor_id),
        "left_on": scholar.left_on,
        "left_reason": scholar.left_reason,
        "photo_on_file": await photos.current(session, scholar.id) is not None,
        "research_record": "Download your PhD file from your profile for every record of it.",
    }


async def summary(session: AsyncSession, principal: Principal) -> dict[str, Any]:
    """What Anveshan holds about the caller, for them to read and download (DPDP Act s.11)."""
    user = await session.get(User, principal.user_id)
    assert user is not None
    out: dict[str, Any] = {
        "generated_at": datetime.now(UTC),
        "account": {
            "name": user.full_name,
            "email": user.email,
            "whatsapp_number": user.whatsapp_number,
            "two_factor_login": user.totp_enabled_at is not None,
            "email_muted": list(user.email_muted),
            "whatsapp_muted": list(user.whatsapp_muted),
            "account_created": user.created_at,
            "privacy_notice_read": user.privacy_notice_seen_at,
        },
        "roles": sorted(principal.roles),
    }
    if (
        scholar := await session.get(Scholar, principal.scholar_id)
        if principal.scholar_id
        else None
    ):
        out["scholar"] = await _scholar_part(session, scholar)
    if principal.faculty_id and (faculty := await session.get(Faculty, principal.faculty_id)):
        out["faculty"] = {
            "employee_id": faculty.employee_id,
            "designation": faculty.designation,
            "department": await session.scalar(
                select(OrgUnit.name).where(OrgUnit.id == faculty.unit_id)
            ),
            "supervises_up_to": faculty.max_scholars,
        }
    sig = await signatures.current(session, user.id)
    out["specimen_signature"] = (
        {"uploaded_at": sig.created_at, "confirmed_at": sig.confirmed_at} if sig else None
    )
    out["files_you_uploaded"] = await session.scalar(
        select(func.count())
        .select_from(FileRow)
        .where(FileRow.uploaded_by == user.id, FileRow.deleted_at.is_(None))
    )
    out["sent_to_outside_services"] = processors()
    out["your_requests"] = [_request_out(r, None) for r in await _requests_of(session, user.id)]
    return out


# --- requests ------------------------------------------------------------------------------


def _request_out(r: DataRequest, name: str | None) -> dict[str, Any]:
    return {
        "id": r.id,
        "kind": r.kind,
        "details": r.details,
        "status": r.status,
        "reply": r.reply,
        "created_at": r.created_at,
        "answered_at": r.answered_at,
        "requester": name,
    }


async def _requests_of(session: AsyncSession, user_id: uuid.UUID) -> list[DataRequest]:
    return list(
        await session.scalars(
            select(DataRequest)
            .where(DataRequest.user_id == user_id, DataRequest.deleted_at.is_(None))
            .order_by(DataRequest.created_at.desc())
        )
    )


async def mine(session: AsyncSession, principal: Principal) -> list[dict[str, Any]]:
    return [_request_out(r, None) for r in await _requests_of(session, principal.user_id)]


async def all_requests(session: AsyncSession, principal: Principal) -> list[dict[str, Any]]:
    """Every request, open ones first, for whoever answers them."""
    if not await handles(session, principal):
        raise forbidden()
    rows = await session.execute(
        select(DataRequest, User.full_name)
        .join(User, User.id == DataRequest.user_id)
        .where(DataRequest.deleted_at.is_(None))
        .order_by(DataRequest.status.desc(), DataRequest.created_at)
    )
    return [_request_out(r, name) for r, name in rows]


async def ask(
    session: AsyncSession, principal: Principal, kind: str, details: str
) -> dict[str, Any]:
    request = await insert(
        session,
        principal,
        DataRequest(user_id=principal.user_id, kind=kind, details=details, status="open"),
    )
    notify(
        session,
        [h for h in await handlers(session) if h != principal.user_id],
        "data_request",
        "A request about personal data",
        f"From {principal.full_name}",
        "/data-requests",
    )
    return _request_out(request, None)


async def answer(
    session: AsyncSession, principal: Principal, request_id: uuid.UUID, reply: str
) -> dict[str, Any]:
    if not await handles(session, principal):
        raise forbidden()
    request = await session.get(DataRequest, request_id, with_for_update=True)
    if request is None or request.deleted_at is not None:
        raise ApiError(404, "not_found", "No such request.")
    if request.status != "open":
        raise ApiError(409, "already_answered", "This request has already been answered.")
    await update(
        session,
        principal,
        request,
        {
            "status": "answered",
            "reply": reply,
            "answered_at": datetime.now(UTC),
            "answered_by": principal.user_id,
        },
    )
    notify(
        session,
        [request.user_id],
        "data_request",
        "Your request about your personal data was answered",
        link="/account#your-data",
    )
    return _request_out(request, None)
