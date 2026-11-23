"""Records an office verifies, or returns with a note, without an approval chain: faculty
publications (the Library, faculty_papers.py) and patents (the office the university chose,
patents.py). The state lives in VerificationColumns (models/research.py): waiting -> verified,
or returned -> corrected by the author -> waiting again."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app import notices
from app.auth.principal import Principal
from app.crud import update
from app.errors import ApiError
from app.models.research import VerificationColumns
from app.notify import notify

# What a correction by the author undoes: the record waits for the office again.
BACK_TO_WAITING = {
    "verification": "waiting",
    "return_note": None,
    "checked_at": None,
    "checked_by": None,
}


async def tell_office(
    session: AsyncSession, principal: Principal, role: str, title: str, link: str
) -> None:
    """Everyone in the verifying office but the author themselves."""
    ids = [uuid.UUID(h["id"]) for h in await notices.holders(session, None, role)]
    notify(
        session, [u for u in ids if u != principal.user_id], "approval_waiting", title, link=link
    )


def note_of(record: VerificationColumns) -> str | None:
    """The office's note, shown while the record is back with its author."""
    return record.return_note if record.verification == "returned" else None


async def verify(
    session: AsyncSession,
    principal: Principal,
    record: VerificationColumns,
    changes: dict[str, Any],
    author: uuid.UUID,
    title: str,
    link: str,
) -> None:
    if record.verification != "waiting":
        raise ApiError(
            409, "verification_state", "Only a record waiting to be checked is verified."
        )
    await _stamp(session, principal, record, changes | {"verification": "verified"})
    notify(session, [author], "approved", f"Verified: {title}", link=link)


async def return_(
    session: AsyncSession,
    principal: Principal,
    record: VerificationColumns,
    note: str,
    author: uuid.UUID,
    title: str,
    link: str,
) -> None:
    """Back to the author to correct: waiting, or verified (a later correction)."""
    if record.verification == "returned":
        raise ApiError(409, "verification_state", "This is already back with its author.")
    await _stamp(session, principal, record, {"verification": "returned", "return_note": note})
    notify(session, [author], "sent_back", f"Returned: {title}", note, link=link)


async def _stamp(
    session: AsyncSession, principal: Principal, record: VerificationColumns, changes: dict
) -> None:
    stamp = {"checked_at": datetime.now(UTC), "checked_by": principal.user_id}
    await update(session, principal, record, changes | stamp)
