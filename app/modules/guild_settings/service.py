"""Database operations service for managing Discord Guild Settings."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.guild_settings.models import GuildSettings

logger = logging.getLogger(__name__)


async def get_guild_settings(
    session: AsyncSession,
    guild_id: uuid.UUID,
) -> GuildSettings | None:
    """Retrieves a GuildSettings record by its associated internal guild UUID."""
    stmt = select(GuildSettings).where(GuildSettings.guild_id == guild_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_guild_settings(
    session: AsyncSession,
    guild_id: uuid.UUID,
) -> tuple[GuildSettings, bool]:
    """Retrieves existing GuildSettings or creates and persists default settings.

    Uses a nested transaction (SAVEPOINT) during creation so that unique constraint
    race conditions roll back only the savepoint without invalidating the outer transaction.

    Returns:
        tuple[GuildSettings, bool]: A tuple containing the GuildSettings instance and a boolean
                                    flag indicating whether the settings were newly created (True)
                                    or pre-existing (False).
    """
    existing_settings = await get_guild_settings(session, guild_id)
    if existing_settings is not None:
        return existing_settings, False

    # Attempt creation using a nested transaction (SAVEPOINT)
    try:
        async with session.begin_nested():
            new_settings = GuildSettings(
                guild_id=guild_id,
                feature_enabled=True,
            )
            session.add(new_settings)
            await session.flush()
        return new_settings, True
    except IntegrityError:
        # Savepoint was automatically rolled back by begin_nested().
        # Outer transaction remains healthy. Re-query for the concurrently created record.
        existing_settings = await get_guild_settings(session, guild_id)
        if existing_settings is not None:
            return existing_settings, False
        raise


async def update_guild_settings(
    session: AsyncSession,
    guild_id: uuid.UUID,
    feature_enabled: bool | None = None,
) -> GuildSettings:
    """Updates configuration settings for the specified internal guild UUID.

    Creates default settings if they do not already exist, and updates only explicitly
    provided settings fields without overwriting unspecified values.
    """
    settings, _ = await get_or_create_guild_settings(session, guild_id)

    updated = False
    if feature_enabled is not None and settings.feature_enabled != feature_enabled:
        settings.feature_enabled = feature_enabled
        updated = True

    if updated:
        await session.flush()

    return settings
