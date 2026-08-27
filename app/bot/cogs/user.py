"""Discord bot cog providing user profile and identity management commands."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from app.database.session import get_session_factory
from app.modules.users.service import get_or_create_user

logger = logging.getLogger(__name__)


class UserCog(commands.Cog):
    """Cog handling user identity creation and profile retrieval commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="profile",
        description="Create or retrieve your Refind Cloud profile.",
    )
    async def profile(self, interaction: discord.Interaction) -> None:
        """Slash command creating or retrieving the invoking Discord user's profile."""
        discord_user = interaction.user
        discord_user_id = discord_user.id
        username = discord_user.name
        global_name = discord_user.global_name or discord_user.display_name

        session_factory = get_session_factory()
        async with session_factory() as session:
            async with session.begin():
                user, created = await get_or_create_user(
                    session=session,
                    discord_user_id=discord_user_id,
                    username=username,
                    global_name=global_name,
                )

        status_label = "New profile created!" if created else "Profile retrieved."
        display_name = f" ({user.global_name})" if user.global_name else ""

        response_text = (
            f"**Refind Cloud User Profile**\n"
            f"• **Status**: {status_label}\n"
            f"• **Username**: `{user.username}`{display_name}\n"
            f"• **Discord User ID**: `{user.discord_user_id}`\n"
            f"• **Refind Cloud ID**: `{user.id}`"
        )

        logger.info(
            f"Profile command executed by {discord_user} (ID: {discord_user_id}). Created: {created}",
            extra={
                "guild_id": interaction.guild_id,
                "user_id": discord_user_id,
                "interaction_id": interaction.id,
            },
        )

        await interaction.response.send_message(
            response_text,
            ephemeral=False,
        )


async def setup(bot: commands.Bot) -> None:
    """Extension setup entry point for UserCog registration."""
    await bot.add_cog(UserCog(bot))
