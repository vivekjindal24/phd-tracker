"""University-wide settings: co-supervision, module switches, approval chains (root admin)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import current_principal, require_root_admin
from app.auth.principal import Principal
from app.crud import update
from app.db import get_session
from app.enums import ItemType, ModuleKey
from app.models import ApprovalChain, Module, Settings
from app.schemas import ChainIn, ModuleUpdate, SettingsOut, SettingsUpdate

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
            "co_supervision": settings.co_supervision,
            "require_hardcopy": settings.require_hardcopy,
            "seminar_graders": settings.seminar_graders,
            "seminar_rubric": settings.seminar_rubric,
            "min_coursework_credits": settings.min_coursework_credits,
            "min_coursework_cgpa": settings.min_coursework_cgpa,
            "max_duration_years": settings.max_duration_years,
            "max_extension_days": settings.max_extension_days,
            "max_relaxation_days": settings.max_relaxation_days,
            "max_maternity_leave_days": settings.max_maternity_leave_days,
            "modules": modules,
            "chains": chains,
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
    await update(session, principal, row, {**changes, "updated_by": principal.user_id})
    await session.commit()
    return await _read(session)


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
