import asyncio
from logging.config import fileConfig

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import settings
from app.models import Base
from app.models.base import SCHEMA

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _run(connection: Connection) -> None:
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        include_schemas=True,
        version_table_schema=SCHEMA,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _main() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
        await connection.commit()
    await engine.dispose()


asyncio.run(_main())
