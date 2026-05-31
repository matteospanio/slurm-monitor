"""Alembic environment for the slurmhub history database.

Designed to be driven programmatically from
:func:`slurmhub.db.engine._run_migrations`, which injects a live connection via
``config.attributes["connection"]``. Sharing the connection is essential for the
in-memory demo database (a fresh engine would migrate a throwaway ``:memory:``
DB). ``render_as_batch=True`` keeps future SQLite ``ALTER`` migrations working.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from slurmhub.db.models import Base

config = context.config

# Only configure logging if invoked via a real alembic.ini (i.e. the dev CLI);
# the programmatic path passes a bare Config with no file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _run(connection) -> None:  # noqa: ANN001
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection", None)
    if connectable is not None:
        _run(connectable)
        return

    # Fallback for the dev CLI (`alembic upgrade head` from a checkout).
    section = config.get_section(config.config_ini_section, {})
    engine = engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with engine.connect() as connection:
        _run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
