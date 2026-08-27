"""Database operations service for managing Discord GuildMemberRole relationships."""

import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.guild_member_roles.models import GuildMemberRole

logger = logging.getLogger(__name__)


async def get_guild_member_role(
    session: AsyncSession,
    guild_member_id: uuid.UUID,
    role_id: uuid.UUID,
) -> GuildMemberRole | None:
    """Retrieves a GuildMemberRole record by internal guild_member_id and role_id."""
    stmt = select(GuildMemberRole).where(
        GuildMemberRole.guild_member_id == guild_member_id,
        GuildMemberRole.role_id == role_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def assign_guild_member_role(
    session: AsyncSession,
    guild_member_id: uuid.UUID,
    role_id: uuid.UUID,
) -> tuple[GuildMemberRole, bool]:
    """Assigns a role to a guild member or retrieves the existing assignment record.

    Uses PostgreSQL ON CONFLICT DO NOTHING for atomic, conflict-safe insertion
    without raising IntegrityError or invalidating active transactions on duplicates.

    Returns:
        tuple[GuildMemberRole, bool]: A tuple containing the GuildMemberRole instance and a boolean
                                     flag indicating whether the relationship was newly created (True)
                                     or pre-existing (False).
    """
    stmt = (
        pg_insert(GuildMemberRole)
        .values(
            guild_member_id=guild_member_id,
            role_id=role_id,
        )
        .on_conflict_do_nothing(
            index_elements=["guild_member_id", "role_id"],
        )
    )
    result = await session.execute(stmt)
    created = result.rowcount > 0

    record = await get_guild_member_role(session, guild_member_id, role_id)
    if record is None:
        raise RuntimeError(
            f"Failed to retrieve GuildMemberRole record for member {guild_member_id} and role {role_id} after assignment."
        )

    return record, created


async def remove_guild_member_role(
    session: AsyncSession,
    guild_member_id: uuid.UUID,
    role_id: uuid.UUID,
) -> bool:
    """Removes a role assignment from a guild member if it exists.

    Uses a direct DELETE query returning whether a row was affected.

    Returns:
        bool: True if the relationship was found and deleted, False if it did not exist.
    """
    stmt = delete(GuildMemberRole).where(
        GuildMemberRole.guild_member_id == guild_member_id,
        GuildMemberRole.role_id == role_id,
    )
    result = await session.execute(stmt)
    return result.rowcount > 0
