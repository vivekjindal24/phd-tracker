"""External thesis reviewers (PRD M3, UX Flow 8c). The Exam Office runs invitations; a link needing
no login accepts or declines; a reviewer account reaches only `/reviewer`. Thesis copies are issued
through /internal for the export service, which stamps them."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import reviews, thesis
from app.auth.deps import current_principal, current_reviewer
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.errors import forbidden
from app.models import ThesisReview, ThesisReviewComment
from app.modules import require_module
from app.schemas.research import (
    InvitationAccept,
    InvitationAccepted,
    InvitationDecline,
    InvitationView,
    ReviewComment,
    ReviewCommentIn,
    ReviewCopyTrace,
    ReviewDetail,
    ReviewInviteIn,
    ReviewRow,
    ReviewSubmitIn,
    ReviewSummary,
    ReviewUpdate,
)

router = APIRouter(tags=["reviews"], dependencies=[Depends(require_module("documents"))])


# --- the Exam Office ------------------------------------------------------------------------


async def _office_ctx(session: AsyncSession, principal: Principal, thesis_id: uuid.UUID):
    thesis.require_office(principal, "exam_office")
    ctx = await thesis.load_thesis(session, principal, thesis_id, lock=True)
    thesis.require_not_guide(principal, ctx)
    return ctx


async def _office_review(
    session: AsyncSession, principal: Principal, review_id: uuid.UUID
) -> ThesisReview:
    thesis.require_office(principal, "exam_office")
    review = await session.get(ThesisReview, review_id)
    if review is None or review.deleted_at is not None:
        raise forbidden()
    await _office_ctx(session, principal, review.thesis_id)
    return review


@router.post("/theses/{thesis_id}/reviews", response_model=ReviewRow, status_code=201)
async def invite_reviewer(
    thesis_id: uuid.UUID,
    body: ReviewInviteIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> ThesisReview:
    ctx = await _office_ctx(session, principal, thesis_id)
    thesis.require_approved(ctx)
    review, raw = await reviews.invite(session, principal, thesis_id, body.model_dump())
    await session.commit()
    await reviews.send_invitation(session, review, raw)
    return review


@router.patch("/reviews/{review_id}", response_model=ReviewRow)
async def update_review(
    review_id: uuid.UUID,
    body: ReviewUpdate,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> ThesisReview:
    """A later deadline reopens access; the reviewer hears of it."""
    review = await _office_review(session, principal, review_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "deadline" in changes:
        reviews.check_deadline(changes["deadline"])
    await update(session, principal, review, changes)
    if "deadline" in changes and review.reviewer_user_id:
        reviews.notify(
            session,
            [review.reviewer_user_id],
            "system",
            "Your review deadline has changed",
            f"It is now {review.deadline:%d %b %Y}.",
            f"/review/{review.id}",
        )
    await session.commit()
    return review


@router.post("/reviews/{review_id}/resend", response_model=ReviewRow)
async def resend_invitation(
    review_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> ThesisReview:
    review = await _office_review(session, principal, review_id)
    review, raw = await reviews.reissue(session, principal, review)
    await session.commit()
    await reviews.send_invitation(session, review, raw)
    return review


@router.get("/review-copies/{code}", response_model=ReviewCopyTrace)
async def trace_copy(
    code: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    thesis.require_office(principal, "exam_office")
    view = await reviews.trace_copy(session, principal, code)
    await session.commit()
    return view


# --- the invitation link: no login ----------------------------------------------------------


@router.get("/review-invitations/{token}", response_model=InvitationView)
async def read_invitation(
    token: str, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    return await reviews.invitation_view(session, await reviews.by_token(session, token))


@router.post("/review-invitations/{token}/accept", response_model=InvitationAccepted)
async def accept_invitation(
    token: str, _: InvitationAccept, session: AsyncSession = Depends(get_session)
) -> dict[str, bool]:
    return await reviews.accept(session, await reviews.by_token(session, token))


@router.post("/review-invitations/{token}/decline", status_code=204)
async def decline_invitation(
    token: str, body: InvitationDecline, session: AsyncSession = Depends(get_session)
) -> None:
    await reviews.decline(session, await reviews.by_token(session, token), body.reason)
    await session.commit()


# --- the reviewer ---------------------------------------------------------------------------


async def _detail(session: AsyncSession, review: ThesisReview) -> dict[str, Any]:
    return {
        **await reviews.summary(session, review),
        "abstract": review.abstract,
        "allow_download": review.allow_download,
        "comments": await reviews.comments_of(session, review.id),
    }


@router.get("/reviewer/reviews", response_model=list[ReviewSummary])
async def my_reviews(
    principal: Principal = Depends(current_reviewer),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = await session.scalars(
        select(ThesisReview)
        .where(
            ThesisReview.reviewer_user_id == principal.user_id,
            ThesisReview.deleted_at.is_(None),
        )
        .order_by(ThesisReview.deadline)
    )
    return [await reviews.summary(session, r) for r in rows.all()]


@router.get("/reviewer/reviews/{review_id}", response_model=ReviewDetail)
async def my_review(
    review_id: uuid.UUID,
    principal: Principal = Depends(current_reviewer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _detail(session, await reviews.own_review(session, principal, review_id))


@router.post(
    "/reviewer/reviews/{review_id}/comments", response_model=ReviewComment, status_code=201
)
async def add_comment(
    review_id: uuid.UUID,
    body: ReviewCommentIn,
    principal: Principal = Depends(current_reviewer),
    session: AsyncSession = Depends(get_session),
) -> ThesisReviewComment:
    review = await reviews.own_review(session, principal, review_id)
    reviews.require_open(review)
    comment = await insert(
        session, principal, ThesisReviewComment(review_id=review.id, **body.model_dump())
    )
    await session.commit()
    return comment


@router.delete("/reviewer/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: uuid.UUID,
    principal: Principal = Depends(current_reviewer),
    session: AsyncSession = Depends(get_session),
) -> None:
    comment = await session.get(ThesisReviewComment, comment_id)
    if comment is None or comment.deleted_at is not None:
        raise forbidden()
    reviews.require_open(await reviews.own_review(session, principal, comment.review_id))
    await soft_delete(session, principal, comment)
    await session.commit()


@router.post("/reviewer/reviews/{review_id}/submit", response_model=ReviewSummary)
async def submit_review(
    review_id: uuid.UUID,
    body: ReviewSubmitIn,
    principal: Principal = Depends(current_reviewer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    review = await reviews.own_review(session, principal, review_id)
    await reviews.submit(session, principal, review, body.recommendation)
    await session.commit()
    return await reviews.summary(session, review)
