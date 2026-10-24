"""University-email login: OpenID Connect authorization code + PKCE with Google or Microsoft
(SECURITY.md §1). SSO only finds an existing active account by verified email — it never
creates one — so switching a leaver's university account off ends their logins here too.

Flow: /start stores state + nonce + PKCE verifier and redirects to the provider; /callback
verifies the id_token and redirects the browser to the web app with a single-use 60-second
code (never tokens in a URL); the web app trades that code at /exchange for a token pair."""

import base64
import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import OidcProvider, settings
from app.errors import ApiError
from app.models import SsoState, User

log = logging.getLogger("anveshan.sso")
STATE_TTL = timedelta(minutes=10)
EXCHANGE_TTL = timedelta(seconds=60)
HTTP_TIMEOUT_S = 10
ID_TOKEN_ALGORITHMS = ["RS256"]


class SsoFailure(Exception):
    """Ends a callback: the browser goes back to /login with this code as `sso_error`."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def configured_providers() -> list[str]:
    return sorted(settings.sso.providers) if settings.sso else []


def provider(name: str) -> OidcProvider:
    p = settings.sso.providers.get(name) if settings.sso else None
    if p is None:
        raise ApiError(404, "sso_not_configured", "This sign-in option is not set up here.")
    return p


def redirect_uri(name: str) -> str:
    assert settings.sso is not None
    return f"{settings.sso.api_public_url}/api/v1/auth/sso/{name}/callback"


async def _get_json(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
        res = await client.get(url)
        res.raise_for_status()
        return res.json()


async def _post_form(url: str, form: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
        res = await client.post(url, data=form)
        res.raise_for_status()
        return res.json()


async def _discovery(p: OidcProvider) -> dict[str, Any]:
    # ponytail: fetched per login (two small GETs); cache with a TTL if logins get busy.
    doc = await _get_json(p.discovery_url)
    if doc.get("issuer") != p.issuer:
        raise SsoFailure("sso_failed", f"unexpected issuer {doc.get('issuer')!r}")
    return doc


async def start(session: AsyncSession, name: str) -> str:
    """Returns the provider's authorization URL for a fresh, stored attempt."""
    p = provider(name)
    try:
        doc = await _discovery(p)
    except (httpx.HTTPError, ValueError, SsoFailure) as exc:
        log.warning("sso discovery for %s failed: %s", name, exc)
        raise ApiError(502, "sso_unavailable", "The sign-in service is not answering.") from exc
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    session.add(
        SsoState(
            provider=name,
            state_hash=_hash(state),
            nonce=nonce,
            code_verifier=verifier,
            expires_at=datetime.now(UTC) + STATE_TTL,
        )
    )
    await session.commit()
    query = {
        "client_id": p.client_id,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": redirect_uri(name),
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge.decode().rstrip("="),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{doc['authorization_endpoint']}?{urlencode(query)}"


async def _verified_claims(p: OidcProvider, doc: dict[str, Any], id_token: str) -> dict[str, Any]:
    try:
        kid = jwt.get_unverified_header(id_token).get("kid")
        keys = (await _get_json(doc["jwks_uri"])).get("keys", [])
        jwk = next((k for k in keys if k.get("kid") == kid), None)
        if jwk is None:
            raise SsoFailure("sso_failed", "id_token signed with an unknown key")
        return jwt.decode(
            id_token,
            jwt.PyJWK(jwk).key,
            algorithms=ID_TOKEN_ALGORITHMS,
            audience=p.client_id,
            issuer=p.issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.InvalidTokenError as exc:
        raise SsoFailure("sso_failed", f"id_token rejected: {exc}") from exc


def _email(p: OidcProvider, claims: dict[str, Any]) -> str:
    """The email the provider vouches for. Google: only when `email_verified`. Microsoft has no
    such claim: the token must come from the university's own tenant, whose admins own it."""
    if p.name == "google":
        email = claims.get("email") if claims.get("email_verified") is True else None
    else:
        if claims.get("tid") != p.tenant_id:
            raise SsoFailure("sso_failed", "token from another Microsoft tenant")
        email = claims.get("email") or claims.get("preferred_username")
    if not isinstance(email, str) or "@" not in email:
        raise SsoFailure("no_verified_email")
    email = email.strip().lower()
    assert settings.sso is not None
    if email.rsplit("@", 1)[1] not in settings.sso.allowed_domains:
        raise SsoFailure("domain_not_allowed")
    return email


async def _user_for(session: AsyncSession, p: OidcProvider, code: str, row: SsoState) -> User:
    try:
        doc = await _discovery(p)
        tokens = await _post_form(
            doc["token_endpoint"],
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri(p.name),
                "client_id": p.client_id,
                "client_secret": p.client_secret,
                "code_verifier": row.code_verifier,
            },
        )
        claims = await _verified_claims(p, doc, str(tokens.get("id_token", "")))
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise SsoFailure("sso_failed", f"provider exchange failed: {exc}") from exc
    if claims.get("nonce") != row.nonce:
        raise SsoFailure("sso_failed", "nonce mismatch")
    email = _email(p, claims)
    user = await session.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None or not user.is_active:
        raise SsoFailure("no_account")
    return user


async def callback(
    session: AsyncSession, name: str, code: str | None, state: str | None, error: str | None
) -> str:
    """Always answers with a URL on the web app's /login: a one-time code, or an error code."""
    login_url = f"{settings.app_base_url}/login"
    try:
        p = provider(name)
        if error:
            raise SsoFailure("cancelled", f"provider said {error}")
        if not code or not state:
            raise SsoFailure("sso_failed", "callback without code or state")
        row = await session.scalar(
            select(SsoState)
            .where(SsoState.state_hash == _hash(state), SsoState.provider == name)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if row is None or row.callback_at is not None or row.expires_at <= now:
            raise SsoFailure("expired")
        row.callback_at = now
        await session.commit()  # the state is spent even if what follows fails
        user = await _user_for(session, p, code, row)
        one_time = secrets.token_urlsafe(32)
        row.user_id, row.exchange_hash = user.id, _hash(one_time)
        row.expires_at = now + EXCHANGE_TTL
        await session.commit()
        return f"{login_url}?{urlencode({'sso_code': one_time})}"
    except ApiError as exc:
        log.warning("sso via %s refused: %s", name, exc.message)
        return f"{login_url}?{urlencode({'sso_error': 'sso_failed'})}"
    except SsoFailure as exc:
        log.warning("sso via %s failed: %s", name, exc)
        return f"{login_url}?{urlencode({'sso_error': exc.code})}"


async def exchange(session: AsyncSession, one_time: str) -> uuid.UUID:
    row = await session.scalar(
        select(SsoState).where(SsoState.exchange_hash == _hash(one_time)).with_for_update()
    )
    now = datetime.now(UTC)
    if row is None or row.exchanged_at is not None or row.expires_at <= now or not row.user_id:
        raise ApiError(401, "invalid_sso_code", "That sign-in has expired. Please try again.")
    row.exchanged_at = now
    user = await session.get(User, row.user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise ApiError(401, "invalid_sso_code", "That sign-in has expired. Please try again.")
    return user.id
