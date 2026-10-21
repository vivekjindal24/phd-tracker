from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import update
from app.db import get_session
from app.errors import ApiError
from app.models import Module, OrgUnit, User
from app.notify import unread_count
from app.schemas import (
    ChangePasswordIn,
    EmailMutedIn,
    LoginIn,
    MeOut,
    RefreshIn,
    TokenPair,
    UnitRoleOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
async def login(body: LoginIn, session: AsyncSession = Depends(get_session)) -> TokenPair:
    access, refresh = await service.login(session, body.email, body.password)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshIn, session: AsyncSession = Depends(get_session)) -> TokenPair:
    access, new_refresh = await service.rotate_refresh(session, body.refresh_token)
    return TokenPair(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=204)
async def logout(body: RefreshIn, session: AsyncSession = Depends(get_session)) -> None:
    await service.revoke_refresh(session, body.refresh_token)


@router.get("/me", response_model=MeOut)
async def me(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    user = await session.get(User, principal.user_id)
    assert user is not None
    unit_names = dict(
        (
            await session.execute(
                select(OrgUnit.id, OrgUnit.name).where(
                    OrgUnit.id.in_([r.unit_id for r in principal.unit_roles])
                )
            )
        ).all()
    )
    modules = dict((await session.execute(select(Module.key, Module.enabled))).all())
    return MeOut(
        id=principal.user_id,
        email=principal.email,
        full_name=principal.full_name,
        roles=sorted(principal.roles),
        unit_roles=[
            UnitRoleOut(
                role=r.role,
                unit_id=r.unit_id,
                unit_name=unit_names.get(r.unit_id, ""),
                unit_path=r.unit_path,
            )
            for r in principal.unit_roles
        ],
        office_roles=sorted(principal.office_roles),
        faculty_id=principal.faculty_id,
        scholar_id=principal.scholar_id,
        is_root_admin=principal.is_root_admin,
        co_supervision=principal.co_supervision,
        modules=modules,
        unread_notifications=await unread_count(session, principal.user_id),
        email_muted=list(user.email_muted),
    )


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    user = await session.get(User, principal.user_id)
    assert user is not None
    if not service.verify_password(user.password_hash, body.current_password):
        raise ApiError(422, "wrong_password", "Your current password is incorrect.")
    await update(
        session, principal, user, {"password_hash": service.hash_password(body.new_password)}
    )
    await service.revoke_all_refresh(session, user.id)
    await session.commit()


@router.put("/me/email-muted", status_code=204)
async def set_email_muted(
    body: EmailMutedIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    user = await session.get(User, principal.user_id)
    assert user is not None
    await update(session, principal, user, {"email_muted": sorted(set(body.email_muted))})
    await session.commit()
