"""Notifications and email delivery (PRD F5, TESTING.md §1.6)."""

import dataclasses

import aiosmtplib
import pytest
from sqlalchemy import select

from app import notify
from app.config import ConfigError, Smtp, _load_smtp, settings
from app.models import Notification
from tests.conftest import auth

SMTP = Smtp(host="smtp.test", port=587, user="u", password="p", mail_from="noreply@x.edu")


@pytest.fixture
def sent(monkeypatch):
    """Email configured; outgoing messages captured instead of sent."""
    monkeypatch.setattr(notify, "settings", dataclasses.replace(settings, smtp=SMTP))
    outbox = []

    async def fake_send(msg):
        outbox.append(msg)

    monkeypatch.setattr(notify, "_send", fake_send)
    return outbox


async def _row(session, user):
    return await session.scalar(select(Notification).where(Notification.user_id == user.id))


async def _notify_and_deliver(session, user, category="approval_waiting"):
    notify.notify(
        session,
        [user.id],
        category,
        "Progress report waiting for you",
        "Supervisor step",
        "/items/progress_report/abc",
    )
    await session.commit()
    await notify.deliver_pending(session)


async def test_email_sent_after_commit_with_absolute_link(session, world, sent):
    await _notify_and_deliver(session, world.meera)
    assert len(sent) == 1
    msg = sent[0]
    assert msg["To"] == "meera@x.edu"
    assert msg["From"] == "Anveshan <noreply@x.edu>"
    assert msg["Subject"] == "Anveshan: Progress report waiting for you"
    assert f"{settings.app_base_url}/items/progress_report/abc" in msg.get_content()
    assert (await _row(session, world.meera)).email_status == "sent"


async def test_muted_category_skips_email_but_keeps_in_app(session, world, sent):
    world.meera.email_muted = ["approval_waiting"]
    session.add(world.meera)
    await session.commit()
    await _notify_and_deliver(session, world.meera)
    assert sent == []
    assert (await _row(session, world.meera)).email_status == "muted"


async def test_without_smtp_the_reason_is_recorded(session, world, monkeypatch):
    monkeypatch.setattr(notify, "settings", dataclasses.replace(settings, smtp=None))
    await _notify_and_deliver(session, world.meera)
    row = await _row(session, world.meera)
    assert (row.email_status, row.email_error) == ("not_sent", notify.NOT_CONFIGURED)


async def test_smtp_failure_is_recorded_not_raised(session, world, monkeypatch):
    monkeypatch.setattr(notify, "settings", dataclasses.replace(settings, smtp=SMTP))

    async def broken(_msg):
        raise aiosmtplib.SMTPAuthenticationError(535, "bad credentials")

    monkeypatch.setattr(notify, "_send", broken)
    await _notify_and_deliver(session, world.meera)
    row = await _row(session, world.meera)
    assert row.email_status == "failed" and "bad credentials" in row.email_error


async def test_rolled_back_event_sends_nothing(session, world, sent):
    meera_id = world.meera.id  # the rollback expires every loaded object
    notify.notify(session, [meera_id], "system", "Will be rolled back")
    await session.rollback()
    await notify.deliver_pending(session)
    assert sent == []
    count = await session.scalar(select(Notification.id).where(Notification.user_id == meera_id))
    assert count is None


async def test_duplicate_recipients_get_one_notification(session, world, sent):
    notify.notify(session, [world.meera.id, world.meera.id], "system", "Once")
    await session.commit()
    await notify.deliver_pending(session)
    assert len(sent) == 1


async def test_inbox_lists_only_own_and_marks_read(client, session, world):
    notify.notify(session, [world.meera.id], "system", "For Meera")
    notify.notify(session, [world.scholar_a1.id], "system", "For Arun")
    await session.commit()
    inbox = (await client.get("/api/v1/notifications", headers=auth(world.meera.id))).json()
    assert [n["title"] for n in inbox] == ["For Meera"]
    other = await session.scalar(
        select(Notification.id).where(Notification.user_id == world.scholar_a1.id)
    )
    denied = await client.post(f"/api/v1/notifications/{other}/read", headers=auth(world.meera.id))
    assert denied.status_code == 403
    await client.post("/api/v1/notifications/read-all", headers=auth(world.meera.id))
    me = (await client.get("/api/v1/auth/me", headers=auth(world.meera.id))).json()
    assert me["unread_notifications"] == 0


@pytest.mark.parametrize(
    ("env", "ok"),
    [
        ({}, True),  # none set: email off
        (
            {
                "SMTP_HOST": "h",
                "SMTP_PORT": "587",
                "SMTP_USER": "u",
                "SMTP_PASSWORD": "p",
                "MAIL_FROM": "a@b.c",
            },
            True,
        ),
        ({"SMTP_HOST": "h"}, False),  # partly configured
        (
            {
                "SMTP_HOST": "h",
                "SMTP_PORT": "x",
                "SMTP_USER": "u",
                "SMTP_PASSWORD": "p",
                "MAIL_FROM": "a@b.c",
            },
            False,
        ),
    ],
)
def test_smtp_config_is_all_or_nothing(monkeypatch, env, ok):
    for name in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "MAIL_FROM"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    if ok:
        _load_smtp()
    else:
        with pytest.raises(ConfigError):
            _load_smtp()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@h/db?sslmode=require",
        "postgres://u:p@h/db",
        "postgresql+psycopg://u:p@h/db",
    ],
)
def test_database_url_accepts_neon_format(url):
    from app.config import _normalize_db_url

    assert _normalize_db_url(url).startswith("postgresql+psycopg://u:p@h/db")


def test_database_url_rejects_other_engines():
    from app.config import _normalize_db_url

    with pytest.raises(ConfigError):
        _normalize_db_url("mysql://u:p@h/db")
