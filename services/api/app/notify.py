"""Notifications (PRD F5). The in-app row is written in the same transaction as the event;
email and WhatsApp go out only after that transaction commits, and each channel's outcome is
stored on the row — sent / failed (with the reason) / muted / not configured — never
silently dropped."""

import logging
import uuid
from collections.abc import Iterable
from email.message import EmailMessage
from email.utils import formataddr

import aiosmtplib
import httpx
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Notification, User

log = logging.getLogger("anveshan.notify")
PENDING_KEY = "pending_email"
SMTP_TIMEOUT_S = 20
NOT_CONFIGURED = "Email is not configured on this server."
WHATSAPP_NOT_CONFIGURED = "WhatsApp is not configured on this server."
WHATSAPP_NO_NUMBER = "No WhatsApp number set."
WHATSAPP_TIMEOUT_S = 20
# What WhatsApp says: only the kind of event, never names or content (PRD F5).
WHATSAPP_TEXT: dict[str, str] = {
    "approval_waiting": "An item is waiting for your step",
    "sent_back": "An item was sent back to you",
    "approved": "Your item was approved",
    "apr_due": "A progress report is due",
    "meeting_tomorrow": "You have a supervision meeting tomorrow",
    "fellowship_ending": "A fellowship is ending soon",
    "grant_alert": "A research project needs attention",
    "seminar": "There is an update on a progress seminar",
    "system": "There is a new update for you",
}


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


def email_configured() -> bool:
    return settings.smtp is not None


def whatsapp_configured() -> bool:
    return settings.whatsapp is not None


async def send_email(to: str, subject: str, body: str) -> None:
    """A direct email that is not an inbox notification (set-password links). Raises on
    failure — the caller decides whether the failure may be shown (SECURITY.md §1)."""
    smtp = settings.smtp
    if smtp is None:
        raise RuntimeError(NOT_CONFIGURED)
    msg = EmailMessage()
    msg["From"] = formataddr(("Anveshan", smtp.mail_from))
    msg["To"] = to
    msg["Subject"] = f"Anveshan: {subject}"
    msg.set_content(body)
    await _send(msg)


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


def _whatsapp_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=WHATSAPP_TIMEOUT_S)


def _whatsapp_payload(number: str, row: Notification, template: str, lang: str) -> dict:
    link = f"{settings.app_base_url}{row.link or '/notifications'}"
    params = [{"type": "text", "text": WHATSAPP_TEXT[row.category]}, {"type": "text", "text": link}]
    return {
        "messaging_product": "whatsapp",
        "to": number.removeprefix("+"),
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": lang},
            "components": [{"type": "body", "parameters": params}],
        },
    }


async def _email(row: Notification, email: str, muted: list[str]) -> None:
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


async def _whatsapp(
    client: httpx.AsyncClient, row: Notification, number: str | None, muted: list[str]
) -> None:
    wa = settings.whatsapp
    if wa is None:
        row.whatsapp_status, row.whatsapp_error = "not_sent", WHATSAPP_NOT_CONFIGURED
    elif number is None:
        row.whatsapp_status, row.whatsapp_error = "not_sent", WHATSAPP_NO_NUMBER
    elif row.category in muted:
        row.whatsapp_status = "muted"
    else:
        try:
            resp = await client.post(
                wa.messages_url,
                headers={"Authorization": f"Bearer {wa.token}"},
                json=_whatsapp_payload(number, row, wa.template, wa.template_lang),
            )
            if resp.is_success:
                row.whatsapp_status, row.whatsapp_error = "sent", None
                return
            reason = _meta_error(resp)
        except httpx.HTTPError as exc:
            reason = str(exc) or type(exc).__name__
        row.whatsapp_status, row.whatsapp_error = "failed", reason[:500]
        log.warning("WhatsApp to user %s failed: %s", row.user_id, reason)


def _meta_error(resp: httpx.Response) -> str:
    try:
        return f"{resp.status_code}: {resp.json()['error']['message']}"
    except (ValueError, KeyError, TypeError):
        return f"{resp.status_code}: {resp.text[:200]}"


async def deliver_pending(session: AsyncSession) -> None:
    """Email and WhatsApp the notifications this (now committed) session created."""
    pending: list[Notification] = session.info.pop(PENDING_KEY, [])
    if not pending:
        return
    # ponytail: sends inline after commit, one SMTP session / HTTP call per message; move
    # to a queue if a single request ever fans out to hundreds of recipients.
    # Rows from a rolled-back transaction never reached the database: skip them.
    ids = [row.id for row in pending if inspect(row).persistent]
    if not ids:
        return
    rows = (
        await session.execute(
            select(
                Notification,
                User.email,
                User.email_muted,
                User.whatsapp_number,
                User.whatsapp_muted,
            )
            .join(User, User.id == Notification.user_id)
            .where(Notification.id.in_(ids))
        )
    ).all()
    async with _whatsapp_client() as client:
        for row, email, email_muted, number, whatsapp_muted in rows:
            await _email(row, email, email_muted)
            await _whatsapp(client, row, number, whatsapp_muted)
    await session.commit()
