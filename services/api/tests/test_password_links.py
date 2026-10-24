"""Set-password links: invite and forgot password (PRD F2, SECURITY.md §1)."""

import dataclasses
import re

import pytest
from sqlalchemy import select

from app import notify
from app.config import Smtp, settings
from app.models import AuditLog, RefreshToken, User
from tests.conftest import auth

SMTP = Smtp(host="smtp.test", port=587, user="u", password="p", mail_from="noreply@x.edu")


@pytest.fixture
def outbox(monkeypatch):
    monkeypatch.setattr(notify, "settings", dataclasses.replace(settings, smtp=SMTP))
    sent = []

    async def fake_send(msg):
        sent.append(msg)

    monkeypatch.setattr(notify, "_send", fake_send)
    return sent


def _token(msg) -> str:
    match = re.search(r"/set-password\?token=([\w-]+)", msg.get_content())
    assert match, msg.get_content()
    return match.group(1)


async def _set(client, token, password="a-brand-new-password"):
    return await client.post(
        "/api/v1/auth/set-password", json={"token": token, "password": password}
    )


async def test_admin_creates_scholar_without_password_and_invite_arrives(client, world, outbox):
    res = await client.post(
        "/api/v1/users",
        headers=auth(world.admin_a1.id),
        json={
            "email": "new@x.edu",
            "full_name": "New Scholar",
            "scholar": {"unit_id": str(world.a1.id), "roll_number": "PHD-NEW-1"},
        },
    )
    assert res.status_code == 201
    assert res.json()["has_password"] is False
    assert outbox[0]["To"] == "new@x.edu"
    # No password yet: password login fails, the link works and logs straight in.
    bad = await client.post("/api/v1/auth/login", json={"email": "new@x.edu", "password": "x"})
    assert bad.status_code == 401
    ok = await _set(client, _token(outbox[0]))
    assert ok.status_code == 200 and ok.json()["access_token"]
    login = await client.post(
        "/api/v1/auth/login", json={"email": "new@x.edu", "password": "a-brand-new-password"}
    )
    assert login.status_code == 200


async def test_without_email_an_admin_must_set_a_password(client, world, monkeypatch):
    monkeypatch.setattr(notify, "settings", dataclasses.replace(settings, smtp=None))
    res = await client.post(
        "/api/v1/users",
        headers=auth(world.admin_a1.id),
        json={
            "email": "new@x.edu",
            "full_name": "New Scholar",
            "scholar": {"unit_id": str(world.a1.id), "roll_number": "PHD-NEW-1"},
        },
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "email_not_configured"


async def test_link_is_single_use_and_revokes_sessions(client, session, world, outbox):
    res = await client.post("/api/v1/auth/forgot-password", json={"email": "Meera@x.edu"})
    assert res.status_code == 204
    token = _token(outbox[0])
    assert (await _set(client, token)).status_code == 200
    again = await _set(client, token)
    assert again.status_code == 422
    assert again.json()["error"]["code"] == "invalid_link"
    # The password change is audited, and its hash redacted.
    row = await session.scalar(
        select(AuditLog).where(
            AuditLog.table_name == "users", AuditLog.record_id == str(world.meera.id)
        )
    )
    assert row is not None and row.data["password_hash"] == "[redacted]"


async def test_a_newer_link_replaces_the_older(client, world, outbox):
    await client.post("/api/v1/auth/forgot-password", json={"email": "meera@x.edu"})
    await client.post("/api/v1/auth/forgot-password", json={"email": "meera@x.edu"})
    first, second = _token(outbox[0]), _token(outbox[1])
    assert (await _set(client, first)).status_code == 422
    assert (await _set(client, second)).status_code == 200


async def test_forgot_password_answers_the_same_for_unknown_email(client, world, outbox):
    res = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@x.edu"})
    assert res.status_code == 204
    assert outbox == []


async def test_forgot_password_shares_the_login_throttle(client, world, outbox):
    for _ in range(5):
        await client.post("/api/v1/auth/forgot-password", json={"email": "meera@x.edu"})
    res = await client.post("/api/v1/auth/forgot-password", json={"email": "meera@x.edu"})
    assert res.status_code == 429


async def test_deactivated_user_cannot_use_a_link(client, session, world, outbox):
    await client.post("/api/v1/auth/forgot-password", json={"email": "scholar_b1@x.edu"})
    user = await session.get(User, world.scholar_b1.id)
    user.is_active = False
    await session.commit()
    assert (await _set(client, _token(outbox[0]))).status_code == 422


async def test_set_password_logs_out_other_devices(client, session, world, outbox):
    login = await client.post(
        "/api/v1/auth/login", json={"email": "meera@x.edu", "password": "correct-horse-battery"}
    )
    old_refresh = login.json()["refresh_token"]
    await client.post("/api/v1/auth/forgot-password", json={"email": "meera@x.edu"})
    await _set(client, _token(outbox[0]))
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert res.status_code == 401
    live = await session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == world.meera.id, RefreshToken.revoked_at.is_(None)
        )
    )
    assert len(list(live)) == 1  # only the session the link itself opened


async def test_invite_is_admin_over_the_user_only(client, world, outbox):
    other_unit = await client.post(
        f"/api/v1/users/{world.scholar_b1.id}/invite", headers=auth(world.admin_a1.id)
    )
    assert other_unit.status_code == 403
    scholar = await client.post(
        f"/api/v1/users/{world.scholar_a1b.id}/invite", headers=auth(world.scholar_a1.id)
    )
    assert scholar.status_code == 403
    ok = await client.post(
        f"/api/v1/users/{world.scholar_a1b.id}/invite", headers=auth(world.admin_a1.id)
    )
    assert ok.status_code == 204
    assert outbox[0]["To"] == "scholar_a1b@x.edu"


async def test_failed_invite_email_is_reported_to_the_admin(client, world, monkeypatch):
    monkeypatch.setattr(notify, "settings", dataclasses.replace(settings, smtp=SMTP))

    async def broken(msg):
        raise OSError("connection refused")

    monkeypatch.setattr(notify, "_send", broken)
    res = await client.post(
        f"/api/v1/users/{world.scholar_a1b.id}/invite", headers=auth(world.admin_a1.id)
    )
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "email_failed"
