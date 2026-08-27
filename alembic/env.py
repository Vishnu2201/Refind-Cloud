"""Async Alembic environment configuration."""

import asyncio
from logging.config import fileConfig
import sys

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.database.base import Base
# Import all ORM models to populate Base.metadata for autogenerate
import app.modules.guild_member_roles.models  # noqa: F401
import app.modules.guild_members.models  # noqa: F401
import app.modules.guild_settings.models  # noqa: F401
import app.modules.guilds.models  # noqa: F401
import app.modules.roles.models  # noqa: F401
import app.modules.users.models  # noqa: F401

# Alembic Config object providing access to alembic.ini values
config = context.config

# Interpret config file for Python logging if required logging sections exist
if config.config_file_name and config.file_config:
    has_logging_sections = (
        config.file_config.has_section("loggers")
        and config.file_config.has_section("handlers")
        and config.file_config.has_section("formatters")
    )
    if has_logging_sections:
        fileConfig(config.config_file_name)

# Set target metadata for 'autogenerate' support
target_metadata = Base.metadata

# Explicitly load database URL from application Settings without swallowing errors
try:
    settings = get_settings()
    config.set_main_option("sqlalchemy.url", settings.database_url_str)
except Exception as exc:
    print(f"CRITICAL: Failed to load application settings for Alembic: {exc}", file=sys.stderr)
    raise RuntimeError(
        f"Alembic migration failed to load application configuration: {exc}"
    ) from exc


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode without an active database connection."""
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("No database connection URL configured for offline Alembic migration.")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Executes migrations using an active database connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Creates async engine and executes migrations online."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async connection."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
