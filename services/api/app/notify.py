"""Notifications (PRD F5). The in-app row is written in the same transaction as the event;
email goes out only after that transaction commits, and its outcome is stored on the row —
sent / failed (with the reason) / muted / not configured — never silently dropped."""

import logging
import uuid
from collections.abc import Iterable
from email.message import EmailMessage
from email.utils import formataddr

import aiosmtplib
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Notification, User

log = logging.getLogger("anveshan.notify")
PENDING_KEY = "pending_email"
SMTP_TIMEOUT_S = 20
NOT_CONFIGURED = "Email is not configured on this server."


def notify(
    session: AsyncSession,
    user_ids: Iterable[uuid.UUID],
    category: str,
    title: str,
    body: str = "",
    link: str | None = None,
) -> None:
    pending: list[Notification] = session.info.setdefault(PENDING_KEY, [])
    for user_id in dict.fromkeys(user_ids):  # de-duplicate, keep order
        row = Notification(user_id=user_id, category=category, title=title, body=body, link=link)
        session.add(row)
        pending.append(row)


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    return count or 0


def _message(to: str, row: Notification, mail_from: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr(("Anveshan", mail_from))
    msg["To"] = to
    msg["Subject"] = f"Anveshan: {row.title}"
    lines = [row.title, ""]
    if row.body:
        lines += [row.body, ""]
    if row.link:
        lines += [f"Open it: {settings.app_base_url}{row.link}", ""]
    lines.append("You can turn off this kind of email in your Anveshan notification settings.")
    msg.set_content("\n".join(lines))
    return msg


async def _send(msg: EmailMessage) -> None:
    smtp = settings.smtp
    assert smtp is not None
    await aiosmtplib.send(
        msg,
        hostname=smtp.host,
        port=smtp.port,
        username=smtp.user,
        password=smtp.password,
        use_tls=smtp.port == 465,
        start_tls=smtp.port != 465,
        timeout=SMTP_TIMEOUT_S,
    )


async def deliver_pending(session: AsyncSession) -> None:
    """Email the notifications this (now committed) session created."""
    pending: list[Notification] = session.info.pop(PENDING_KEY, [])
    if not pending:
        return
    # ponytail: sends inline after commit, one SMTP session per mail; move to a queue if a
    # single request ever fans out to hundreds of recipients.
    # Rows from a rolled-back transaction never reached the database: skip them.
    ids = [row.id for row in pending if inspect(row).persistent]
    if not ids:
        return
    rows = (
        await session.execute(
            select(Notification, User.email, User.email_muted)
            .join(User, User.id == Notification.user_id)
            .where(Notification.id.in_(ids))
        )
    ).all()
    for row, email, muted in rows:
        if row.category in muted:
            row.email_status = "muted"
        elif settings.smtp is None:
            row.email_status, row.email_error = "not_sent", NOT_CONFIGURED
        else:
            try:
                await _send(_message(email, row, settings.smtp.mail_from))
                row.email_status, row.email_error = "sent", None
            except (aiosmtplib.SMTPException, OSError, TimeoutError) as exc:
                row.email_status, row.email_error = "failed", str(exc)[:500]
                log.warning("email to user %s failed: %s", row.user_id, exc)
    await session.commit()
