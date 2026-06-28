"""Async Alembic environment configuration.

Note
----
Alembic loads this file via ``importlib.util.spec_from_file_location`` +
``exec_module``, which does **not** set ``__package__``. Relative imports
therefore fail. We use absolute ``anvil.*`` imports instead, which work
because ``anvil`` is either installed in site-packages or importable via
``prepend_sys_path`` (``alembic.ini``) + the configured script_location.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from anvil.db.base import (  # relative-imports:allow — Alembic loader does not set __package__
    Base,
)
from anvil.db.registry import (  # relative-imports:allow — registers all models on Base.metadata
    get_expected_tables,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
