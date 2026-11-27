"""University-wide settings: co-supervision, module switches, approval chains (root admin)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import apr, branding, dates, grading, notices, phd_index
from app.auth.deps import current_principal, require_root_admin
from app.auth.principal import Principal
from app.crud import update
from app.db import get_session
from app.enums import PHD_FORMS, SEMINAR_KINDS, ItemType, ModuleKey
from app.errors import ApiError, forbidden
from app.models import ApprovalChain, Module, ProgressReport, Settings
from app.notify import email_configured
from app.schemas import ChainIn, ExamControllerIn, ModuleUpdate, SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


async def _read(session: AsyncSession) -> SettingsOut:
    settings = await session.get(Settings, 1)
    assert settings is not None, "settings row is seeded by migration 0001"
    modules = dict((await session.execute(select(Module.key, Module.enabled))).all())
    chains = dict(
        (await session.execute(select(ApprovalChain.item_type, ApprovalChain.steps))).all()
    )
    return SettingsOut.model_validate(
        {
            "university_address": settings.university_address,
            "department_committee_name": settings.department_committee_name,
            "co_supervision": settings.co_supervision,
            "require_hardcopy": settings.require_hardcopy,
            "require_no_dues": settings.require_no_dues,
            "require_ethics": settings.require_ethics,
            "require_two_factor": settings.require_two_factor,
            "require_signing": settings.require_signing,
            "apr_custom_template": settings.apr_custom_template,
            "apr_sections": settings.apr_sections,
            "apr_template": apr.effective(settings),
            "seminar_graders": settings.seminar_graders,
            "seminar_rubric": settings.seminar_rubric,
            "seminar_forms": {k: grading.form_for(settings, k) for k in SEMINAR_KINDS},
            "phd_forms": {k: settings.phd_forms.get(k, {}) for k in PHD_FORMS},
            "phd_form_defaults": PHD_FORMS,
            "phd_index": settings.phd_index,
            "exam_controller_id": settings.exam_controller_id,
            "date_format": settings.date_format,
            "phd_sources": phd_index.sources(),
            "min_coursework_credits": settings.min_coursework_credits,
            "min_coursework_cgpa": settings.min_coursework_cgpa,
            "max_duration_years": settings.max_duration_years,
            "max_extension_days": settings.max_extension_days,
            "max_relaxation_days": settings.max_relaxation_days,
            "max_maternity_leave_days": settings.max_maternity_leave_days,
            "min_duration_years": settings.min_duration_years,
            "max_plagiarism_percent": settings.max_plagiarism_percent,
            "min_publications": settings.min_publications,
            "publications_indexed_only": settings.publications_indexed_only,
            "publication_file_required": settings.publication_file_required,
            "patent_verifier": settings.patent_verifier,
            "grievance_appeals_to": settings.grievance_appeals_to,
            "modules": modules,
            "chains": chains,
            "email_configured": email_configured(),
        }
    )


@router.get("", response_model=SettingsOut)
async def get_settings(
    _: Principal = Depends(current_principal), session: AsyncSession = Depends(get_session)
) -> SettingsOut:
    return await _read(session)


@router.patch("", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdate,
    principal: Principal = Depends(require_root_admin),
    session: AsyncSession = Depends(get_session),
) -> SettingsOut:
    row = await session.get(Settings, 1)
    assert row is not None
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "seminar_forms" in changes:  # one kind at a time: keep the others as they are
        changes["seminar_forms"] = {**row.seminar_forms, **changes["seminar_forms"]}
    wrong = phd_index.problems(changes.get("phd_index", []))
    if wrong:
        raise ApiError(422, "index_invalid", "; ".join(wrong))
    if "phd_forms" in changes:  # likewise one form at a time; an all-empty form is dropped
        merged = {**row.phd_forms, **changes["phd_forms"]}
        changes["phd_forms"] = {k: v for k, v in merged.items() if any(v.values())}
    await update(session, principal, row, {**changes, "updated_by": principal.user_id})
    await session.commit()
    if "date_format" in changes:
        dates.use(changes["date_format"])  # at once here; other workers within a minute
    return await _read(session)


@router.put("/exam-controller", response_model=SettingsOut)
async def set_exam_controller(
    body: ExamControllerIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> SettingsOut:
    """Who signs notices as the Controller of Examinations, for the whole university: chosen by
    the Exam Office or the root admin among those in the Exam Office."""
    if not notices.sets_controller(principal):
        raise forbidden()
    await notices.set_controller(session, principal, body.user_id)
    await session.commit()
    return await _read(session)


@router.put("/logo", status_code=204)
async def set_logo(
    request: Request,
    principal: Principal = Depends(require_root_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    content, content_type = await branding.read_image_upload(request, "logo")
    await branding.replace_logo(session, principal, content, content_type)
    await session.commit()


@router.delete("/logo", status_code=204)
async def remove_logo(
    principal: Principal = Depends(require_root_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    await branding.remove_logo(session, principal)
    await session.commit()


@router.put("/modules/{key}", response_model=SettingsOut)
async def set_module(
    key: ModuleKey,
    body: ModuleUpdate,
    principal: Principal = Depends(require_root_admin),
    session: AsyncSession = Depends(get_session),
) -> SettingsOut:
    row = await session.get(Module, key)
    assert row is not None, "module rows are seeded by migration 0001"
    await update(
        session, principal, row, {"enabled": body.enabled, "updated_by": principal.user_id}
    )
    await session.commit()
    return await _read(session)


async def _check_committee_step(
    session: AsyncSession, item_type: str, old: list[dict], new: list[str]
) -> None:
    """The advisory committee step reviews progress reports only (PRD F9b). While a report on
    its way carries the step, it stays in the chain: its signers read reports only while the
    chain has it (scope.py)."""
    if "committee" in new and item_type != "progress_report":
        raise ApiError(
            422,
            "committee_step_reports_only",
            "The advisory committee step can be added to the progress report chain only.",
        )
    removing = any(s["kind"] == "committee" for s in old) and "committee" not in new
    if removing and await session.scalar(
        select(ProgressReport.id)
        .where(
            ProgressReport.deleted_at.is_(None),
            ProgressReport.state.in_(("in_review", "sent_back")),
            ProgressReport.chain_snapshot.contains([{"kind": "committee"}]),
        )
        .limit(1)
    ):
        raise ApiError(
            409,
            "committee_step_in_use",
            "Progress reports under review still pass the advisory committee step. Remove it "
            "once they are approved.",
        )


@router.put("/chains/{item_type}", response_model=SettingsOut)
async def set_chain(
    item_type: ItemType,
    body: ChainIn,
    principal: Principal = Depends(require_root_admin),
    session: AsyncSession = Depends(get_session),
) -> SettingsOut:
    """Applies to new submissions only: in-flight items keep their chain_snapshot."""
    row = await session.get(ApprovalChain, item_type)
    assert row is not None, "chains are seeded by migration 0001"
    await _check_committee_step(session, item_type, row.steps, [s.kind for s in body.steps])
    await update(
        session,
        principal,
        row,
        {
            "steps": [s.model_dump() for s in body.steps],
            "updated_by": principal.user_id,
        },
    )
    await session.commit()
    return await _read(session)
