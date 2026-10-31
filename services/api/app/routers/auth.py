from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service, sso
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import update
from app.db import get_session
from app.enums import SsoProvider
from app.errors import ApiError
from app.models import Module, OrgUnit, User
from app.notify import unread_count, whatsapp_configured
from app.schemas import (
    ChangePasswordIn,
    EmailMutedIn,
    ForgotPasswordIn,
    LoginIn,
    MeOut,
    RefreshIn,
    SetPasswordIn,
    SsoExchangeIn,
    TokenPair,
    UnitRoleOut,
    WhatsappIn,
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


@router.post("/forgot-password", status_code=204)
async def forgot_password(
    body: ForgotPasswordIn, session: AsyncSession = Depends(get_session)
) -> None:
    await service.forgot_password(session, body.email)


@router.post("/set-password", response_model=TokenPair)
async def set_password(
    body: SetPasswordIn, session: AsyncSession = Depends(get_session)
) -> TokenPair:
    """Consumes an invite / reset link and logs the person straight in."""
    user_id = await service.set_password_with_link(session, body.token, body.password)
    access, refresh = await service.issue_tokens(session, user_id)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.get("/sso/providers", response_model=list[SsoProvider])
async def sso_providers() -> list[str]:
    return sso.configured_providers()


@router.get("/sso/{provider}/start")
async def sso_start(
    provider: SsoProvider, session: AsyncSession = Depends(get_session)
) -> RedirectResponse:
    return RedirectResponse(await sso.start(session, provider), status_code=302)


@router.get("/sso/{provider}/callback")
async def sso_callback(
    provider: SsoProvider,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    return RedirectResponse(
        await sso.callback(session, provider, code, state, error), status_code=302
    )


@router.post("/sso/exchange", response_model=TokenPair)
async def sso_exchange(
    body: SsoExchangeIn, session: AsyncSession = Depends(get_session)
) -> TokenPair:
    user_id = await sso.exchange(session, body.code)
    access, refresh = await service.issue_tokens(session, user_id)
    return TokenPair(access_token=access, refresh_token=refresh)


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
        whatsapp_available=whatsapp_configured(),
        whatsapp_number=user.whatsapp_number,
        whatsapp_muted=list(user.whatsapp_muted),
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


@router.put("/me/whatsapp", status_code=204)
async def set_whatsapp(
    body: WhatsappIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    user = await session.get(User, principal.user_id)
    assert user is not None
    changes = {
        "whatsapp_number": body.whatsapp_number,
        "whatsapp_muted": sorted(set(body.whatsapp_muted)),
    }
    await update(session, principal, user, changes)
    await session.commit()
