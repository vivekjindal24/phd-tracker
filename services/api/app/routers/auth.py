from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import dates, privacy
from app.auth import service, sso
from app.auth.deps import any_principal, current_principal
from app.auth.principal import Principal
from app.config import settings
from app.crud import update
from app.db import get_session
from app.enums import SsoProvider
from app.errors import ApiError
from app.models import Module, OrgUnit, User
from app.notify import unread_count, whatsapp_configured
from app.schemas import (
    AccessToken,
    ChangePasswordIn,
    EmailMutedIn,
    ForgotPasswordIn,
    LoginIn,
    MeOut,
    SetPasswordIn,
    SsoExchangeIn,
    UnitRoleOut,
    WhatsappIn,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# The refresh token lives only in this cookie (SECURITY.md §7): httpOnly, so no script can read
# it; SameSite=Strict, so no other site can make the browser send it; and sent only to these
# routes. Secure wherever the portal is served over https.
REFRESH_COOKIE = service.REFRESH_COOKIE
COOKIE_PATH = "/api/v1/auth"


def _signed_in(
    response: Response, access: str, refresh: str, recovery: list[str] | None = None
) -> AccessToken:
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=settings.refresh_token_days * 86_400,
        path=COOKIE_PATH,
        secure=settings.app_base_url.startswith("https://"),
        httponly=True,
        samesite="strict",
    )
    return AccessToken(access_token=access, recovery_codes=recovery)


def _expired() -> ApiError:
    return ApiError(401, "invalid_token", "Your session has expired. Please log in.")


@router.post("/login", response_model=AccessToken)
async def login(
    body: LoginIn, response: Response, session: AsyncSession = Depends(get_session)
) -> AccessToken:
    access, refresh, recovery = await service.login(session, body.email, body.password, body.code)
    return _signed_in(response, access, refresh, recovery)


@router.post("/refresh", response_model=AccessToken)
async def refresh(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> AccessToken:
    if not (raw := request.cookies.get(REFRESH_COOKIE)):
        raise _expired()
    access, new_refresh = await service.rotate_refresh(session, raw)
    return _signed_in(response, access, new_refresh)


@router.post("/logout", status_code=204)
async def logout(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> None:
    if raw := request.cookies.get(REFRESH_COOKIE):
        await service.revoke_refresh(session, raw)
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH, httponly=True, samesite="strict")


@router.post("/forgot-password", status_code=204)
async def forgot_password(
    body: ForgotPasswordIn, session: AsyncSession = Depends(get_session)
) -> None:
    await service.forgot_password(session, body.email)


@router.post("/set-password", response_model=AccessToken)
async def set_password(
    body: SetPasswordIn, response: Response, session: AsyncSession = Depends(get_session)
) -> AccessToken:
    """Consumes an invite / reset link and logs the person straight in."""
    user_id = await service.set_password_with_link(session, body.token, body.password)
    if await service.two_factor_required(session):  # an emailed link must not skip the code
        await session.commit()
        raise ApiError(403, "login_required", "Your password is set. Log in with it to continue.")
    access, refresh = await service.issue_tokens(session, user_id)
    return _signed_in(response, access, refresh)


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


@router.post("/sso/exchange", response_model=AccessToken)
async def sso_exchange(
    body: SsoExchangeIn, response: Response, session: AsyncSession = Depends(get_session)
) -> AccessToken:
    user_id = await sso.exchange(session, body.code)
    access, refresh = await service.issue_tokens(session, user_id)
    return _signed_in(response, access, refresh)


@router.get("/me", response_model=MeOut)
async def me(
    principal: Principal = Depends(any_principal),
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
        is_reviewer=principal.is_reviewer,
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
        date_format=dates.current(),
        modules=modules,
        unread_notifications=await unread_count(session, principal.user_id),
        email_muted=list(user.email_muted),
        whatsapp_available=whatsapp_configured(),
        whatsapp_number=user.whatsapp_number,
        whatsapp_muted=list(user.whatsapp_muted),
        privacy_notice_due=await privacy.notice_due(session, user),
        answers_data_requests=await privacy.handles(session, principal),
    )


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordIn,
    principal: Principal = Depends(any_principal),
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
    principal: Principal = Depends(any_principal),
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
