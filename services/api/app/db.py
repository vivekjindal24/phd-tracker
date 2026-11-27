from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.notify import deliver_pending


def _startup_options() -> str:
    """Every connection carries the key the audit trail is sealed with (migration 0068), set as
    the connection starts so no rollback can undo it. It shows in no query text and is never
    stored in the database."""
    key = settings.audit_key.replace("\\", "\\\\").replace(" ", "\\ ")
    return f"-c anveshan.audit_key={key}"


engine = create_async_engine(
    settings.database_url,
    pool_size=2,
    max_overflow=3,
    pool_pre_ping=True,
    connect_args={"options": _startup_options()},
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
        # Only reached when the request succeeded: emails for committed notifications.
        await deliver_pending(session)
