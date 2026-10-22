"""Seminar grading, supervisor review, AI draft, finalise; the scholar's to-do list
(PRD F15, UX Flow 6b)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai, grading, scope, seminars
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import insert, update
from app.db import get_session
from app.enums import TODO_PART_LABELS, TodoStatus
from app.errors import ApiError, forbidden
from app.models import Faculty, Scholar, SeminarGrade, SeminarPanel, Settings, Todo, User
from app.notify import notify
from app.rbac import require_perm
from app.schemas import DraftIn, FinaliseIn, GradeIn, ReviewView, TodoOut, TodoUpdate

router = APIRouter(tags=["seminar grading"])


async def _rubric(session: AsyncSession) -> list[dict[str, Any]]:
    settings = await session.get(Settings, 1)
    assert settings is not None
    return settings.seminar_rubric


async def _review(
    session: AsyncSession, principal: Principal, seminar_id: uuid.UUID, scholar_id: uuid.UUID
) -> dict[str, Any]:
    seminar, path = await seminars.get_seminar(session, principal, seminar_id)
    entry, scholar = await grading.load_entry(session, seminar.id, scholar_id)
    await grading.require_review_access(session, principal, seminar, path, entry, scholar)
    rows = await session.execute(
        select(SeminarGrade, User.full_name)
        .join(Faculty, Faculty.id == SeminarGrade.grader_id)
        .join(User, User.id == Faculty.user_id)
        .where(SeminarGrade.seminar_scholar_id == entry.id, SeminarGrade.deleted_at.is_(None))
        .order_by(SeminarGrade.submitted_at)
    )
    grades, mine = [], None
    for g, name in rows:
        view = {
            "grader": name,
            "scores": g.scores,
            "rubric": g.rubric,
            "total": sum(g.scores.values()),
            "max_total": sum(c["max"] for c in g.rubric),
            "comment": g.comment,
            "submitted_at": g.submitted_at,
        }
        grades.append(view)
        if g.grader_id == principal.faculty_id:
            mine = view
    pct = [g["total"] / g["max_total"] * 100 for g in grades if g["max_total"]]
    todos = []
    if entry.finalised_at:
        todos = list(
            await session.scalars(
                select(Todo).where(
                    Todo.source_seminar_scholar_id == entry.id, Todo.deleted_at.is_(None)
                )
            )
        )
    is_grader = await grading.is_grader(session, principal, seminar.id)
    finaliser = grading.can_finalise(principal, scholar)
    name = await session.scalar(select(User.full_name).where(User.id == scholar.user_id))
    return {
        "seminar_id": seminar.id,
        "seminar_title": seminar.title,
        "scholar": {"id": scholar.id, "name": name},
        "rubric": await _rubric(session),
        "grades": grades,
        "average_percent": round(sum(pct) / len(pct), 1) if pct else None,
        "draft_points": (entry.draft_points or []) if finaliser else [],
        "finalised_at": entry.finalised_at,
        "todos": [TodoOut.model_validate(t, from_attributes=True) for t in todos],
        "can_grade": is_grader and seminar.status == "scheduled" and entry.finalised_at is None,
        "my_grade": mine,
        "can_finalise": finaliser and entry.finalised_at is None,
        "ai_available": ai.available(),
        "parts": TODO_PART_LABELS,
    }


async def _finaliser_entry(session, principal, seminar_id, scholar_id):
    seminar, _ = await seminars.get_seminar(session, principal, seminar_id)
    entry, scholar = await grading.load_entry(session, seminar.id, scholar_id)
    if not grading.can_finalise(principal, scholar):
        raise forbidden()
    if entry.finalised_at is not None:
        raise ApiError(422, "already_finalised", "This review has already been finalised.")
    return seminar, entry, scholar


@router.post("/seminars/{seminar_id}/attend", status_code=204)
async def attend(
    seminar_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Any faculty may join as an attending grader when the university allows it."""
    if principal.faculty_id is None:
        raise forbidden()
    if not await seminars.open_to_faculty(session):
        raise ApiError(
            422, "attending_not_allowed", "Only the named panel grades seminars at this university."
        )
    seminar, _ = await seminars.get_seminar(session, principal, seminar_id)
    if seminar.status != "scheduled":
        raise ApiError(422, "seminar_cancelled", "This seminar was cancelled.")
    if not await grading.is_grader(session, principal, seminar_id):
        await insert(
            session,
            principal,
            SeminarPanel(seminar_id=seminar_id, faculty_id=principal.faculty_id, kind="attending"),
        )
        await session.commit()


@router.get("/seminars/{seminar_id}/scholars/{scholar_id}/review", response_model=ReviewView)
async def get_review(
    seminar_id: uuid.UUID,
    scholar_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _review(session, principal, seminar_id, scholar_id)


@router.put("/seminars/{seminar_id}/scholars/{scholar_id}/grade", response_model=ReviewView)
async def grade(
    seminar_id: uuid.UUID,
    scholar_id: uuid.UUID,
    body: GradeIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    seminar, _ = await seminars.get_seminar(session, principal, seminar_id)
    if not await grading.is_grader(session, principal, seminar.id):
        raise forbidden()
    if seminar.status != "scheduled":
        raise ApiError(422, "seminar_cancelled", "This seminar was cancelled.")
    entry, _scholar = await grading.load_entry(session, seminar.id, scholar_id)
    if entry.finalised_at is not None:
        raise ApiError(422, "already_finalised", "Grades are locked once the review is finalised.")
    rubric = await _rubric(session)
    scores = grading.validate_scores(rubric, body.scores)
    existing = await session.scalar(
        select(SeminarGrade).where(
            SeminarGrade.seminar_scholar_id == entry.id,
            SeminarGrade.grader_id == principal.faculty_id,
            SeminarGrade.deleted_at.is_(None),
        )
    )
    values = {
        "scores": scores,
        "rubric": rubric,
        "comment": body.comment,
        "submitted_at": datetime.now(UTC),
    }
    if existing:
        await update(session, principal, existing, values)
    else:
        await insert(
            session,
            principal,
            SeminarGrade(seminar_scholar_id=entry.id, grader_id=principal.faculty_id, **values),
        )
    await session.commit()
    return await _review(session, principal, seminar_id, scholar_id)


@router.post("/seminars/{seminar_id}/scholars/{scholar_id}/suggest", response_model=ReviewView)
async def suggest(
    seminar_id: uuid.UUID,
    scholar_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """AI drafts points from all graders' comments into the supervisor's working list."""
    _seminar, entry, _scholar = await _finaliser_entry(session, principal, seminar_id, scholar_id)
    comments = list(
        await session.scalars(
            select(SeminarGrade.comment).where(
                SeminarGrade.seminar_scholar_id == entry.id, SeminarGrade.deleted_at.is_(None)
            )
        )
    )
    if not any(c.strip() for c in comments):
        raise ApiError(422, "no_comments", "There are no grader comments to work from yet.")
    try:
        points = await ai.suggest_points(comments)
    except ai.AiUnavailable as exc:
        raise ApiError(
            503,
            "ai_unavailable",
            f"AI couldn't draft points right now ({exc}). Please write them yourself.",
        ) from exc
    await update(session, principal, entry, {"draft_points": points})
    await session.commit()
    return await _review(session, principal, seminar_id, scholar_id)


@router.put("/seminars/{seminar_id}/scholars/{scholar_id}/draft", response_model=ReviewView)
async def save_draft(
    seminar_id: uuid.UUID,
    scholar_id: uuid.UUID,
    body: DraftIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _seminar, entry, _scholar = await _finaliser_entry(session, principal, seminar_id, scholar_id)
    await update(session, principal, entry, {"draft_points": [p.model_dump() for p in body.points]})
    await session.commit()
    return await _review(session, principal, seminar_id, scholar_id)


@router.post("/seminars/{seminar_id}/scholars/{scholar_id}/finalise", response_model=ReviewView)
async def finalise(
    seminar_id: uuid.UUID,
    scholar_id: uuid.UUID,
    body: FinaliseIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    seminar, entry, scholar = await _finaliser_entry(session, principal, seminar_id, scholar_id)
    graders = list(
        await session.scalars(
            select(Faculty.user_id)
            .join(SeminarGrade, SeminarGrade.grader_id == Faculty.id)
            .where(SeminarGrade.seminar_scholar_id == entry.id, SeminarGrade.deleted_at.is_(None))
        )
    )
    if not graders:
        raise ApiError(422, "no_grades", "Finalise once at least one grader has submitted marks.")
    for point in body.points:
        await insert(
            session,
            principal,
            Todo(
                scholar_id=scholar.id,
                part=point.part,
                text=point.text,
                source_seminar_scholar_id=entry.id,
                created_by=principal.user_id,
            ),
        )
    await update(
        session,
        principal,
        entry,
        {
            "finalised_at": datetime.now(UTC),
            "finalised_by": principal.user_id,
            "draft_points": [p.model_dump() for p in body.points],
        },
    )
    link = f"/seminars/{seminar.id}/review/{scholar.id}"
    notify(
        session,
        [scholar.user_id],
        "seminar",
        "Your seminar feedback is ready",
        f"{len(body.points)} point(s) added to your to-do list.",
        link,
    )
    notify(
        session,
        [u for u in graders if u != principal.user_id],
        "seminar",
        "Seminar review finalised",
        seminar.title,
        link,
    )
    await session.commit()
    return await _review(session, principal, seminar_id, scholar_id)


@router.get("/todos", response_model=list[TodoOut])
async def list_todos(
    scholar_id: uuid.UUID | None = None,
    status: TodoStatus | None = None,
    principal: Principal = Depends(require_perm("todos", "read")),
    session: AsyncSession = Depends(get_session),
) -> list[Todo]:
    stmt = (
        select(Todo)
        .join(Scholar, Scholar.id == Todo.scholar_id)
        .where(Todo.deleted_at.is_(None), scope.scholar_predicate(principal, "todos"))
    )
    if scholar_id:
        stmt = stmt.where(Todo.scholar_id == scholar_id)
    if status:
        stmt = stmt.where(Todo.status == status)
    return list(await session.scalars(stmt.order_by(Todo.status, Todo.part, Todo.created_at)))


@router.patch("/todos/{todo_id}", response_model=TodoOut)
async def tick_todo(
    todo_id: uuid.UUID,
    body: TodoUpdate,
    principal: Principal = Depends(require_perm("todos", "update")),
    session: AsyncSession = Depends(get_session),
) -> Todo:
    todo = await session.scalar(select(Todo).where(Todo.id == todo_id, Todo.deleted_at.is_(None)))
    if todo is None or todo.scholar_id != principal.scholar_id:
        raise forbidden()  # only the scholar ticks their own points
    await update(
        session,
        principal,
        todo,
        {
            "status": body.status,
            "done_at": datetime.now(UTC) if body.status == "done" else None,
        },
    )
    await session.commit()
    return todo
