import os
import sys
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Base  # noqa: E402

config = context.config
if "DATABASE_URL" not in os.environ:
	raise RuntimeError("DATABASE_URL is not set — alembic refuses to guess a target database")
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

target_metadata = Base.metadata


def run_migrations_offline() -> None:
	context.configure(
		url=config.get_main_option("sqlalchemy.url"),
		target_metadata=target_metadata,
		literal_binds=True,
	)
	with context.begin_transaction():
		context.run_migrations()


def run_migrations_online() -> None:
	connectable = engine_from_config(
		config.get_section(config.config_ini_section) or {},
		prefix="sqlalchemy.",
		poolclass=pool.NullPool,
	)
	with connectable.connect() as connection:
		context.configure(connection=connection, target_metadata=target_metadata)
		with context.begin_transaction():
			context.run_migrations()


if context.is_offline_mode():
	run_migrations_offline()
else:
	run_migrations_online()