from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import auth
from tests.world import PASSWORD


async def _login(client, email, password=PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def test_login_returns_token_pair(client, world):
    res = await _login(client, "scholar_a1@x.edu")
    assert res.status_code == 200
    assert res.json()["access_token"] and res.json()["refresh_token"]


async def test_login_is_case_insensitive_on_email(client, world):
    assert (await _login(client, "Scholar_A1@X.edu")).status_code == 200


async def test_wrong_password_is_401_with_envelope(client, world):
    res = await _login(client, "scholar_a1@x.edu", "nope-nope-nope")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_credentials"


async def test_five_failures_throttle_even_the_right_password(client, world):
    for _ in range(5):
        await _login(client, "meera@x.edu", "wrong-password")
    res = await _login(client, "meera@x.edu")
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "too_many_attempts"


async def test_inactive_user_cannot_log_in(client, world, session):
    world.scholar_b1.is_active = False
    session.add(world.scholar_b1)
    await session.commit()
    assert (await _login(client, "scholar_b1@x.edu")).status_code == 401


async def test_refresh_token_is_single_use(client, world):
    first = (await _login(client, "scholar_a1@x.edu")).json()["refresh_token"]
    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401


async def test_logout_revokes_refresh_token(client, world):
    token = (await _login(client, "scholar_a1@x.edu")).json()["refresh_token"]
    assert (
        await client.post("/api/v1/auth/logout", json={"refresh_token": token})
    ).status_code == 204
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert res.status_code == 401


async def test_missing_or_garbage_token_is_401(client, world):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    res = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer junk"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_token"


async def test_me_combines_every_role(client, world):
    me = (await client.get("/api/v1/auth/me", headers=auth(world.meera.id))).json()
    assert set(me["roles"]) == {"supervisor", "unit_head", "admin"}
    assert {(r["role"], r["unit_name"]) for r in me["unit_roles"]} == {
        ("unit_head", "Dept A1"),
        ("admin", "Dept A1"),
    }
    assert me["faculty_id"] == str(world.meera_faculty.id)
    assert me["is_root_admin"] is False
    assert set(me["modules"]) >= {"publications", "ledger"}


async def test_me_for_root_admin_and_scholar(client, world):
    root = (await client.get("/api/v1/auth/me", headers=auth(world.root_admin.id))).json()
    assert root["is_root_admin"] is True
    scholar = (await client.get("/api/v1/auth/me", headers=auth(world.scholar_a1.id))).json()
    assert scholar["roles"] == ["scholar"]
    assert scholar["scholar_id"] == str(world.s_a1.id)


async def test_change_password_revokes_sessions_and_redacts_audit(client, world, session):
    refresh = (await _login(client, "scholar_a1@x.edu")).json()["refresh_token"]
    res = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a-brand-new-passphrase"},
        headers=auth(world.scholar_a1.id),
    )
    assert res.status_code == 204
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    ).status_code == 401
    assert (await _login(client, "scholar_a1@x.edu", "a-brand-new-passphrase")).status_code == 200
    row = await session.scalar(
        select(AuditLog).where(AuditLog.record_id == str(world.scholar_a1.id))
    )
    assert row.data["password_hash"] == "[redacted]"
    assert row.prev["password_hash"] == "[redacted]"


async def test_change_password_needs_current_password(client, world):
    res = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "not-it-at-all", "new_password": "a-brand-new-passphrase"},
        headers=auth(world.scholar_a1.id),
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "wrong_password"


async def test_email_muted_validates_categories(client, world):
    ok = await client.put(
        "/api/v1/auth/me/email-muted",
        json={"email_muted": ["apr_due"]},
        headers=auth(world.scholar_a1.id),
    )
    assert ok.status_code == 204
    bad = await client.put(
        "/api/v1/auth/me/email-muted",
        json={"email_muted": ["not_a_category"]},
        headers=auth(world.scholar_a1.id),
    )
    assert bad.status_code == 422
