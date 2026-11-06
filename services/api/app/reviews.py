"""External thesis reviewers (PRD M3, UX Flow 8c): the invitation, one thesis until the deadline,
and the review. A submitted review becomes an ExaminerReport, so release, examiner confidentiality
and the viva gate keep working from one place (thesis.py). Reviewer accounts are closed everywhere
else by auth/deps.py."""

import logging
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.auth.principal import Principal
from app.auth.service import EMAIL_NOT_CONFIGURED, email_password_link, hash_token
from app.auth.service import issue_password_link as _password_link
from app.branding import public_view
from app.config import settings
from app.crud import audit, insert, update
from app.errors import ApiError, forbidden
from app.grants import IST
from app.models import (
    ExaminerReport,
    FileRow,
    RoleAssignment,
    Scholar,
    ThesisReview,
    ThesisReviewComment,
    ThesisReviewCopy,
    ThesisSubmission,
    User,
)
from app.notify import email_configured, notify, send_email

log = logging.getLogger("anveshan.reviews")
INVITE_TTL = timedelta(days=7)
REMINDER_DAYS = (7, 1)
_LINK_INVALID = ApiError(
    422,
    "invalid_link",
    "This invitation is invalid or has expired. Ask the university for a new one.",
)
_CLOSED = ApiError(409, "review_closed", "This review is closed.")


def today() -> date:
    return datetime.now(IST).date()


def is_open(review: ThesisReview) -> bool:
    return review.status == "accepted" and review.deadline >= today()


def require_open(review: ThesisReview) -> None:
    if not is_open(review):
        raise _CLOSED


def check_deadline(deadline: date) -> None:
    if deadline <= today():
        raise ApiError(422, "invalid_deadline", "The deadline must be after today.")


async def own_review(
    session: AsyncSession, principal: Principal, review_id: uuid.UUID
) -> ThesisReview:
    review = await session.get(ThesisReview, review_id)
    if review is None or review.deleted_at is not None:
        raise forbidden()
    if review.reviewer_user_id != principal.user_id:
        raise forbidden()
    return review


async def _exam_office_ids(session: AsyncSession) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(RoleAssignment.user_id).where(
            RoleAssignment.role == "exam_office", RoleAssignment.deleted_at.is_(None)
        )
    )
    return list(rows)


async def _tell_exam_office(session: AsyncSession, review: ThesisReview, title: str) -> None:
    notify(
        session,
        await _exam_office_ids(session),
        "system",
        title,
        link=f"/items/thesis_submission/{review.thesis_id}",
    )


async def _thesis_title(session: AsyncSession, review: ThesisReview) -> str:
    return await session.scalar(
        select(ThesisSubmission.title).where(ThesisSubmission.id == review.thesis_id)
    )


# --- the invitation -------------------------------------------------------------------------


async def invite(
    session: AsyncSession, principal: Principal, thesis_id: uuid.UUID, fields: dict[str, Any]
) -> tuple[ThesisReview, str]:
    if not email_configured():
        raise EMAIL_NOT_CONFIGURED
    check_deadline(fields["deadline"])
    user = await session.scalar(
        select(User).where(User.email == fields["email"], User.deleted_at.is_(None))
    )
    if user is not None and not user.is_reviewer:
        raise ApiError(
            409, "reviewer_is_staff", "This person already has an account here, so cannot review."
        )
    raw = secrets.token_urlsafe(32)
    review = await insert(
        session,
        principal,
        ThesisReview(
            thesis_id=thesis_id,
            invite_token_hash=hash_token(raw),
            invite_expires_at=datetime.now(UTC) + INVITE_TTL,
            **fields,
        ),
    )
    return review, raw


async def reissue(
    session: AsyncSession, principal: Principal, review: ThesisReview
) -> tuple[ThesisReview, str]:
    if review.status not in ("invited", "expired"):
        raise ApiError(409, "not_resendable", "This invitation has already been answered.")
    raw = secrets.token_urlsafe(32)
    await update(
        session,
        principal,
        review,
        {
            "status": "invited",
            "invite_token_hash": hash_token(raw),
            "invite_expires_at": datetime.now(UTC) + INVITE_TTL,
        },
    )
    return review, raw


async def send_invitation(session: AsyncSession, review: ThesisReview, raw: str) -> None:
    """Called after the commit, so a failed email leaves an invitation that can be resent."""
    university = (await public_view(session))["university"]
    body = "\n".join(
        [
            f"Dear {review.name},",
            "",
            f"{university} invites you to review a PhD thesis.",
            "",
            f"Title: {await _thesis_title(session, review)}",
            f"Abstract: {review.abstract}",
            f"Review deadline: {review.deadline:%d %b %Y}",
            "",
            f"Accept or decline here (the link works for {INVITE_TTL.days} days):",
            f"{settings.app_base_url}/review-invitation/{raw}",
            "",
            "If you did not expect this email, you can ignore it.",
        ]
    )
    try:
        await send_email(review.email, "Invitation to review a PhD thesis", body)
    except Exception as exc:
        raise ApiError(502, "email_failed", f"The invitation could not be sent: {exc}") from exc


async def by_token(session: AsyncSession, raw: str) -> ThesisReview:
    review = await session.scalar(
        select(ThesisReview)
        .where(ThesisReview.invite_token_hash == hash_token(raw))
        .with_for_update()
    )
    live = (
        review is not None
        and review.deleted_at is None
        and review.status == "invited"
        and review.invite_expires_at > datetime.now(UTC)
    )
    if not live:
        raise _LINK_INVALID
    return review  # type: ignore[return-value]


async def invitation_view(session: AsyncSession, review: ThesisReview) -> dict[str, Any]:
    return {
        "university": (await public_view(session))["university"],
        "reviewer_name": review.name,
        "thesis_title": await _thesis_title(session, review),
        "abstract": review.abstract,
        "deadline": review.deadline,
    }


async def accept(session: AsyncSession, review: ThesisReview) -> dict[str, bool]:
    user = await session.scalar(
        select(User).where(User.email == review.email, User.deleted_at.is_(None))
    )
    if user is None:
        user = await insert(
            session, None, User(email=review.email, full_name=review.name, is_reviewer=True)
        )
    elif not user.is_reviewer:
        raise ApiError(409, "reviewer_is_staff", "Please contact the university's Exam Office.")
    await update(
        session,
        None,
        review,
        {
            "status": "accepted",
            "reviewer_user_id": user.id,
            "responded_at": datetime.now(UTC),
            "invite_token_hash": None,
        },
    )
    await _tell_exam_office(session, review, f"{review.name} accepted a thesis review")
    has_password = user.password_hash is not None
    raw = None if has_password else await _password_link(session, user.id, "invite")
    await session.commit()
    if raw is None:
        return {"has_password": True, "email_sent": False}
    try:
        await email_password_link(user, raw, "invite")
    except Exception:
        # Accepted either way: "Forgot your password?" sends a new link, so this is only logged.
        log.exception("set-password email failed for review %s", review.id)
        return {"has_password": False, "email_sent": False}
    return {"has_password": False, "email_sent": True}


async def decline(session: AsyncSession, review: ThesisReview, reason: str) -> None:
    await update(
        session,
        None,
        review,
        {
            "status": "declined",
            "responded_at": datetime.now(UTC),
            "decline_reason": reason or None,
            "invite_token_hash": None,
        },
    )
    await _tell_exam_office(session, review, f"{review.name} declined a thesis review")


# --- the review -----------------------------------------------------------------------------


async def comments_of(session: AsyncSession, review_id: uuid.UUID) -> list[ThesisReviewComment]:
    rows = await session.scalars(
        select(ThesisReviewComment)
        .where(ThesisReviewComment.review_id == review_id, ThesisReviewComment.deleted_at.is_(None))
        .order_by(ThesisReviewComment.page, ThesisReviewComment.created_at)
    )
    return list(rows)


async def _review_files(session: AsyncSession, review_id: uuid.UUID) -> list[FileRow]:
    rows = await session.scalars(
        select(FileRow).where(
            FileRow.table_name == "thesis_reviews",
            FileRow.record_id == review_id,
            FileRow.status == "ready",
            FileRow.deleted_at.is_(None),
        )
    )
    return list(rows)


async def summary(session: AsyncSession, review: ThesisReview) -> dict[str, Any]:
    return {
        "id": review.id,
        "thesis_title": await _thesis_title(session, review),
        "deadline": review.deadline,
        "status": review.status,
        "is_open": is_open(review),
    }


async def submit(
    session: AsyncSession, principal: Principal, review: ThesisReview, recommendation: str
) -> None:
    require_open(review)
    files = await _review_files(session, review.id)
    if not files and not await comments_of(session, review.id):
        raise ApiError(422, "review_is_empty", "Add at least one comment or upload your review.")
    report = await insert(
        session,
        principal,
        ExaminerReport(
            thesis_id=review.thesis_id,
            examiner_name=review.name,
            institution=review.institution,
            received_on=today(),
            recommendation=recommendation,
        ),
    )
    for file in files:
        await update(
            session, principal, file, {"table_name": "examiner_reports", "record_id": report.id}
        )
    await update(
        session,
        principal,
        review,
        {
            "status": "submitted",
            "recommendation": recommendation,
            "submitted_at": datetime.now(UTC),
            "report_id": report.id,
        },
    )
    await _tell_exam_office(session, review, f"{review.name} submitted a thesis review")


# --- copies ---------------------------------------------------------------------------------


async def _thesis_file(session: AsyncSession, review: ThesisReview) -> FileRow:
    """The scholar's own PDF: the Library's certificate hangs off the same record."""
    file = await session.scalar(
        select(FileRow)
        .join(ThesisSubmission, ThesisSubmission.id == FileRow.record_id)
        .join(Scholar, Scholar.id == ThesisSubmission.scholar_id)
        .where(
            FileRow.table_name == "thesis_submissions",
            FileRow.record_id == review.thesis_id,
            FileRow.uploaded_by == Scholar.user_id,
            FileRow.content_type == "application/pdf",
            FileRow.status == "ready",
            FileRow.deleted_at.is_(None),
        )
        .order_by(FileRow.created_at.desc())
    )
    if file is None:
        raise ApiError(409, "thesis_not_pdf", "The thesis is not available as a PDF yet.")
    return file


def _new_code() -> str:
    raw = secrets.token_hex(4).upper()
    return f"{raw[:4]}-{raw[4:]}"


async def issue_copy(
    session: AsyncSession, principal: Principal, review_id: uuid.UUID, *, download: bool
) -> dict[str, Any]:
    review = await own_review(session, principal, review_id)
    require_open(review)
    if download and not review.allow_download:
        raise ApiError(403, "download_not_allowed", "This thesis can only be read here.")
    file = await _thesis_file(session, review)
    copy = await insert(
        session,
        principal,
        ThesisReviewCopy(
            review_id=review.id, code=_new_code(), kind="download" if download else "view"
        ),
    )
    return {
        "code": copy.code,
        "file_url": storage.presign_get(file.storage_key, file.file_name),
        "file_name": file.file_name,
        "download": download,
    }


async def trace_copy(session: AsyncSession, principal: Principal, code: str) -> dict[str, Any]:
    """Whose copy a leaked code was. Each lookup is written to the audit log."""
    row = (
        await session.execute(
            select(ThesisReviewCopy, ThesisReview)
            .join(ThesisReview, ThesisReview.id == ThesisReviewCopy.review_id)
            .where(ThesisReviewCopy.code == code.strip().upper())
        )
    ).first()
    if row is None:
        raise ApiError(404, "not_found", "No copy has this code.")
    copy, review = row
    audit(session, principal, copy, "lookup")
    return {
        "code": copy.code,
        "kind": copy.kind,
        "issued_at": copy.created_at,
        "reviewer_name": review.name,
        "reviewer_email": review.email,
        "institution": review.institution,
        "thesis_title": await _thesis_title(session, review),
    }


# --- the daily job --------------------------------------------------------------------------


async def daily(session: AsyncSession, run_on: date) -> dict[str, int]:
    """Expire unanswered invitations, remind reviewers, and report deadlines that passed."""
    expired = await session.scalars(
        select(ThesisReview).where(
            ThesisReview.status == "invited",
            ThesisReview.deleted_at.is_(None),
            ThesisReview.invite_expires_at <= func.now(),
        )
    )
    expired_count = 0
    for review in expired.all():
        await update(session, None, review, {"status": "expired", "invite_token_hash": None})
        await _tell_exam_office(session, review, f"{review.name} did not answer the invitation")
        expired_count += 1

    # ponytail: exact-day matches, so a day the scheduler misses sends no reminder for that day.
    reminder_days = [run_on + timedelta(days=d) for d in REMINDER_DAYS]
    reminded = await session.scalars(
        select(ThesisReview).where(
            ThesisReview.status == "accepted",
            ThesisReview.deleted_at.is_(None),
            ThesisReview.deadline.in_(reminder_days),
        )
    )
    reminders = 0
    for review in reminded.all():
        notify(
            session,
            [review.reviewer_user_id],
            "system",
            "Your thesis review is due soon",
            f"The deadline is {review.deadline:%d %b %Y}.",
            f"/review/{review.id}",
        )
        reminders += 1

    closed = await session.scalars(
        select(ThesisReview).where(
            ThesisReview.status == "accepted",
            ThesisReview.deleted_at.is_(None),
            ThesisReview.deadline == run_on - timedelta(days=1),
        )
    )
    closed_count = 0
    for review in closed.all():
        await _tell_exam_office(session, review, f"{review.name} missed the review deadline")
        closed_count += 1
    return {
        "review_invites_expired": expired_count,
        "review_reminders": reminders,
        "review_deadlines_missed": closed_count,
    }
