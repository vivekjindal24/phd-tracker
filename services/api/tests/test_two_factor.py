"""Two-factor login (SECURITY.md §1): off unless the university switches it on; then every
password login needs an authenticator code, set up at the first login after the switch."""

import time

from sqlalchemy import select

from app.auth import totp
from app.models import User
from tests.conftest import auth
from tests.world import PASSWORD

API = "/api/v1"


async def switch_on(client, world) -> None:
    res = await client.patch(
        f"{API}/settings", headers=auth(world.root_admin.id), json={"require_two_factor": True}
    )
    assert res.status_code == 200 and res.json()["require_two_factor"] is True


async def login(client, user, code=None, password=PASSWORD):
    body = {"email": user.email, "password": password}
    if code is not None:
        body["code"] = code
    return await client.post(f"{API}/auth/login", json=body)


async def enrolled(client, world, user) -> tuple[str, list[str]]:
    """Switch it on and take `user` through setup; returns the secret and recovery codes."""
    await switch_on(client, world)
    secret = (await login(client, user)).json()["error"]["details"]["secret"]
    done = await login(client, user, totp.code(secret, time.time()))
    assert done.status_code == 200, done.text
    return secret, done.json()["recovery_codes"]


def test_codes_match_the_published_test_vector():
    # RFC 6238 appendix B, SHA-1, T = 59 s: 94287082, of which an app shows the last six.
    secret = totp.base64.b32encode(b"12345678901234567890").decode()
    assert totp.code(secret, 59) == "287082"


async def test_off_by_default_a_password_is_enough(client, world):
    res = await login(client, world.scholar_a1)
    assert res.status_code == 200 and res.json()["recovery_codes"] is None


async def test_first_login_sets_it_up(client, world):
    await switch_on(client, world)
    first = await login(client, world.scholar_a1)
    assert first.status_code == 401
    error = first.json()["error"]
    assert error["code"] == "two_factor_setup_required"
    secret = error["details"]["secret"]
    assert error["details"]["otpauth_uri"].startswith("otpauth://totp/")
    wrong = await login(client, world.scholar_a1, "000000")
    assert wrong.status_code == 401 and wrong.json()["error"]["code"] == "invalid_code"
    done = await login(client, world.scholar_a1, totp.code(secret, time.time()))
    assert done.status_code == 200, done.text
    assert done.json()["access_token"] and len(done.json()["recovery_codes"]) == 8
    # A wrong password still says nothing about two-factor.
    bad = await login(client, world.scholar_a1, password="not-the-password")
    assert bad.json()["error"]["code"] == "invalid_credentials"


async def test_later_logins_need_a_fresh_code(client, world):
    secret, recovery = await enrolled(client, world, world.meera)
    bare = await login(client, world.meera)
    assert bare.status_code == 401 and bare.json()["error"]["code"] == "two_factor_required"
    assert "details" not in bare.json()["error"] or not bare.json()["error"]["details"]
    replay = await login(client, world.meera, totp.code(secret, time.time()))
    assert replay.status_code == 401  # the code that enrolled cannot be used twice
    fresh = await login(client, world.meera, totp.code(secret, time.time() + 30))
    assert fresh.status_code == 200 and fresh.json()["recovery_codes"] is None
    # A recovery code works once.
    assert (await login(client, world.meera, recovery[0])).status_code == 200
    assert (await login(client, world.meera, recovery[0])).status_code == 401


async def test_admin_resets_a_lost_phone(client, session, world):
    await enrolled(client, world, world.scholar_a1)
    url = f"{API}/users/{world.scholar_a1.id}/two-factor/reset"
    for user in (world.scholar_a1, world.hod_b1, world.research_office):
        assert (await client.post(url, headers=auth(user.id))).status_code == 403, user.email
    assert (await client.post(url, headers=auth(world.admin_a1.id))).status_code == 204
    again = await login(client, world.scholar_a1)
    assert again.json()["error"]["code"] == "two_factor_setup_required"
    row = await session.scalar(select(User).where(User.id == world.scholar_a1.id))
    assert row.recovery_hashes == []


async def test_a_password_link_does_not_skip_the_second_step(client, session, world):
    from app.auth import service

    await switch_on(client, world)
    raw = await service.issue_password_link(session, world.scholar_a2.id, "reset")
    await session.commit()
    res = await client.post(
        f"{API}/auth/set-password", json={"token": raw, "password": "a-brand-new-password"}
    )
    assert res.status_code == 403 and res.json()["error"]["code"] == "login_required"
    step = await login(client, world.scholar_a2, password="a-brand-new-password")
    assert step.json()["error"]["code"] == "two_factor_setup_required"
