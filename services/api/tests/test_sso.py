"""University-email login via OpenID Connect (PRD F2, SECURITY.md §1). The provider is faked:
discovery, JWKS and the token endpoint are served from memory, id_tokens signed by a test key."""

import dataclasses
import json
import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import sso
from app.config import OidcProvider, Sso, settings

TENANT = "11111111-2222-3333-4444-555555555555"
GOOGLE = OidcProvider("google", "g-client", "g-secret", "https://accounts.google.com")
MICROSOFT = OidcProvider(
    "microsoft",
    "m-client",
    "m-secret",
    f"https://login.microsoftonline.com/{TENANT}/v2.0",
    TENANT,
)
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = {**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key())), "kid": "k1"}


class FakeProvider:
    def __init__(self) -> None:
        self.claims: dict = {}
        self.token_requests: list[dict] = []

    async def get_json(self, url: str) -> dict:
        for p in (GOOGLE, MICROSOFT):
            if url == p.discovery_url:
                return {
                    "issuer": p.issuer,
                    "authorization_endpoint": f"{p.issuer}/authorize",
                    "token_endpoint": f"{p.issuer}/token",
                    "jwks_uri": f"{p.issuer}/jwks",
                }
        assert url.endswith("/jwks"), url
        return {"keys": [JWK]}

    async def post_form(self, url: str, form: dict) -> dict:
        self.token_requests.append(form)
        p = GOOGLE if url.startswith(GOOGLE.issuer) else MICROSOFT
        now = int(time.time())
        claims = {"iss": p.issuer, "aud": p.client_id, "sub": "s1", "iat": now, "exp": now + 300}
        claims |= self.claims
        token = jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "k1"})
        return {"id_token": token}


@pytest.fixture
def provider(monkeypatch):
    fake = FakeProvider()
    configured = Sso(
        providers={"google": GOOGLE, "microsoft": MICROSOFT},
        allowed_domains=("x.edu",),
        api_public_url="https://api.test",
    )
    monkeypatch.setattr(sso, "settings", dataclasses.replace(settings, sso=configured))
    monkeypatch.setattr(sso, "_get_json", fake.get_json)
    monkeypatch.setattr(sso, "_post_form", fake.post_form)
    return fake


async def _start(client, name="google") -> dict:
    res = await client.get(f"/api/v1/auth/sso/{name}/start")
    assert res.status_code == 302
    return {k: v[0] for k, v in parse_qs(urlparse(res.headers["location"]).query).items()}


async def _callback(client, name, query) -> dict:
    res = await client.get(f"/api/v1/auth/sso/{name}/callback", params=query)
    assert res.status_code == 302
    location = urlparse(res.headers["location"])
    assert location.path == "/login"
    return {k: v[0] for k, v in parse_qs(location.query).items()}


async def _sign_in(client, provider, claims, name="google") -> dict:
    auth_query = await _start(client, name)
    provider.claims = {"nonce": auth_query["nonce"], **claims}
    return await _callback(client, name, {"code": "c1", "state": auth_query["state"]})


async def test_providers_lists_only_configured(client, provider):
    res = await client.get("/api/v1/auth/sso/providers")
    assert res.json() == ["google", "microsoft"]


async def test_google_verified_email_logs_into_existing_account(client, world, provider):
    back = await _sign_in(client, provider, {"email": "Meera@x.edu", "email_verified": True})
    res = await client.post("/api/v1/auth/sso/exchange", json={"code": back["sso_code"]})
    assert res.status_code == 200
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {res.json()['access_token']}"}
    )
    assert me.json()["email"] == "meera@x.edu"
    # PKCE: the token request carried the verifier for the challenge sent at /start.
    assert provider.token_requests[0]["code_verifier"]
    assert provider.token_requests[0]["redirect_uri"].startswith("https://api.test/api/v1/")


async def test_exchange_code_is_single_use(client, world, provider):
    back = await _sign_in(client, provider, {"email": "meera@x.edu", "email_verified": True})
    assert (
        await client.post("/api/v1/auth/sso/exchange", json={"code": back["sso_code"]})
    ).status_code == 200
    again = await client.post("/api/v1/auth/sso/exchange", json={"code": back["sso_code"]})
    assert again.status_code == 401


async def test_unverified_google_email_is_refused(client, world, provider):
    back = await _sign_in(client, provider, {"email": "meera@x.edu", "email_verified": False})
    assert back == {"sso_error": "no_verified_email"}


async def test_unknown_email_never_creates_an_account(client, world, provider):
    back = await _sign_in(client, provider, {"email": "stranger@x.edu", "email_verified": True})
    assert back == {"sso_error": "no_account"}


async def test_deactivated_account_is_refused(client, session, world, provider):
    world.meera.is_active = False
    session.add(world.meera)
    await session.commit()
    back = await _sign_in(client, provider, {"email": "meera@x.edu", "email_verified": True})
    assert back == {"sso_error": "no_account"}


async def test_other_domain_is_refused(client, world, provider):
    back = await _sign_in(client, provider, {"email": "meera@gmail.com", "email_verified": True})
    assert back == {"sso_error": "domain_not_allowed"}


async def test_wrong_nonce_is_refused(client, world, provider):
    auth_query = await _start(client)
    provider.claims = {"nonce": "forged", "email": "meera@x.edu", "email_verified": True}
    back = await _callback(client, "google", {"code": "c1", "state": auth_query["state"]})
    assert back == {"sso_error": "sso_failed"}


async def test_state_is_single_use(client, world, provider):
    auth_query = await _start(client)
    provider.claims = {"nonce": auth_query["nonce"], "email": "meera@x.edu", "email_verified": True}
    await _callback(client, "google", {"code": "c1", "state": auth_query["state"]})
    replay = await _callback(client, "google", {"code": "c1", "state": auth_query["state"]})
    assert replay == {"sso_error": "expired"}


async def test_token_for_another_client_is_refused(client, world, provider):
    back = await _sign_in(
        client, provider, {"aud": "someone-else", "email": "meera@x.edu", "email_verified": True}
    )
    assert back == {"sso_error": "sso_failed"}


async def test_microsoft_must_come_from_the_university_tenant(client, world, provider):
    back = await _sign_in(
        client,
        provider,
        {"tid": "99999999-0000-0000-0000-000000000000", "email": "meera@x.edu"},
        name="microsoft",
    )
    assert back == {"sso_error": "sso_failed"}
    ok = await _sign_in(
        client, provider, {"tid": TENANT, "preferred_username": "meera@x.edu"}, name="microsoft"
    )
    assert "sso_code" in ok


async def test_user_cancelling_at_the_provider(client, world, provider):
    back = await _callback(client, "google", {"error": "access_denied", "state": "x"})
    assert back == {"sso_error": "cancelled"}


async def test_unconfigured_provider_is_404(client, world, monkeypatch):
    monkeypatch.setattr(sso, "settings", dataclasses.replace(settings, sso=None))
    res = await client.get("/api/v1/auth/sso/google/start")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "sso_not_configured"


SSO_ENV = (
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "MICROSOFT_CLIENT_ID",
    "MICROSOFT_CLIENT_SECRET",
    "MICROSOFT_TENANT_ID",
    "SSO_ALLOWED_DOMAINS",
    "API_PUBLIC_URL",
)
FULL_GOOGLE = {
    "GOOGLE_CLIENT_ID": "id",
    "GOOGLE_CLIENT_SECRET": "secret",
    "SSO_ALLOWED_DOMAINS": "x.edu, @Y.ac.in",
    "API_PUBLIC_URL": "https://api.test/",
}


@pytest.mark.parametrize(
    ("env", "error"),
    [
        ({}, None),
        (FULL_GOOGLE, None),
        ({"GOOGLE_CLIENT_ID": "id"}, "partly configured"),
        ({**FULL_GOOGLE, "SSO_ALLOWED_DOMAINS": ""}, "SSO_ALLOWED_DOMAINS"),
        ({**FULL_GOOGLE, "SSO_ALLOWED_DOMAINS": "not a domain"}, "invalid entries"),
        ({**FULL_GOOGLE, "API_PUBLIC_URL": ""}, "API_PUBLIC_URL"),
        (
            {
                **FULL_GOOGLE,
                "MICROSOFT_CLIENT_ID": "m",
                "MICROSOFT_CLIENT_SECRET": "s",
                "MICROSOFT_TENANT_ID": "common",
            },
            "tenant GUID",
        ),
    ],
)
def test_sso_config(monkeypatch, env, error):
    from app.config import ConfigError, _load_sso

    for name in SSO_ENV:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    if error:
        with pytest.raises(ConfigError, match=error):
            _load_sso()
        return
    loaded = _load_sso()
    if env:
        assert loaded is not None
        assert loaded.allowed_domains == ("x.edu", "y.ac.in")
        assert loaded.api_public_url == "https://api.test"
    else:
        assert loaded is None
