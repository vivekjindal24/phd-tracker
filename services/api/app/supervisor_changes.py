"""A change of supervisor through its approval chain (owner, 2026-11-22). The department admin
proposes the new supervisor with the reason (and the scholar's consent, the order); the chain
(Department, Research Office by default) approves; only then does the change happen, kept as
history in supervisor_appointments (supervision.py), and the old supervisor, the new one and
the scholar are told. Items waiting on the supervisor move to the new one by themselves: the
supervisor step always means the scholar's current supervisor."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import dates, directory, supervision
from app.auth.principal import Principal
from app.enums import LOCAL_TZ
from app.errors import ApiError
from app.models import Faculty, SupervisorChange, User
from app.notify import notify
from app.workflow import ItemContext


def content(c: SupervisorChange, _: Principal) -> dict[str, Any]:
    return {
        "scholar_id": c.scholar_id,
        "from": {"id": c.from_faculty_id, "name": c.from_name} if c.from_faculty_id else None,
        "to": {"id": c.to_faculty_id, "name": c.to_name},
        "reason": c.reason,
        "scholar_consent": c.scholar_consent,
        "order_ref": c.order_ref,
        "effective_on": c.effective_on,
    }


def title(c: SupervisorChange) -> str:
    return f"{c.from_name or 'No supervisor'} → {c.to_name}"


async def ready(session: AsyncSession, principal: Principal, ctx: ItemContext) -> None:
    """Still sound to submit or approve: the scholar's supervisor is the one it replaces, and
    the new one may still take the scholar (their limit may have filled meanwhile)."""
    change: SupervisorChange = ctx.item  # type: ignore[assignment]
    if ctx.scholar.supervisor_id != change.from_faculty_id:
        raise ApiError(
            409,
            "supervisor_changed_meanwhile",
            "The scholar's supervisor has changed since this was proposed. Withdraw it and "
            "propose the change again.",
        )
    await directory.check_supervisor(session, ctx.scholar, change.to_faculty_id)


async def approved(session: AsyncSession, principal: Principal, ctx: ItemContext) -> None:
    """The final approval: the change happens, from the order's date (else today)."""
    change: SupervisorChange = ctx.item  # type: ignore[assignment]
    await ready(session, principal, ctx)
    on = change.effective_on or datetime.now(LOCAL_TZ).date()
    await supervision.change(
        session,
        principal,
        ctx.scholar,
        "supervisor",
        change.to_faculty_id,
        on=on,
        order_ref=change.order_ref,
    )
    users = dict(
        (
            await session.execute(
                select(Faculty.id, Faculty.user_id).where(
                    Faculty.id.in_([i for i in (change.from_faculty_id, change.to_faculty_id) if i])
                )
            )
        ).all()
    )
    name = await session.scalar(select(User.full_name).where(User.id == ctx.scholar.user_id))
    link = f"/scholars/{ctx.scholar.id}"
    when = dates.day(on)
    notify(
        session,
        [users[change.to_faculty_id]],
        "system",
        f"{name} is now your scholar",
        f"From {when}.",
        link,
    )
    if change.from_faculty_id in users:
        notify(
            session,
            [users[change.from_faculty_id]],
            "system",
            f"You are no longer {name}'s supervisor",
            f"{change.to_name} supervises them from {when}.",
            link,
        )
    notify(
        session,
        [ctx.scholar.user_id],
        "system",
        "Your supervisor has changed",
        f"{change.to_name} is your supervisor from {when}.",
        link,
    )
