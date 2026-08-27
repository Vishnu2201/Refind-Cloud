"""Ping slash command cog returning real-time websocket latency."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


class PingCog(commands.Cog):
    """Foundation diagnostic cog containing the /ping command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="Check real-time Discord websocket latency.",
    )
    async def ping(self, interaction: discord.Interaction) -> None:
        """Responds with actual Discord websocket gateway latency in milliseconds."""
        latency_ms = round(self.bot.latency * 1000)
        
        logger.info(
            f"Ping command executed by {interaction.user} (ID: {interaction.user.id}). Latency: {latency_ms}ms",
            extra={
                "guild_id": interaction.guild_id,
                "user_id": interaction.user.id,
                "interaction_id": interaction.id,
            },
        )

        await interaction.response.send_message(
            f"Pong! Latency: `{latency_ms}ms`",
            ephemeral=False,
        )


async def setup(bot: commands.Bot) -> None:
    """Extension setup entry point for discord.py cog registration."""
    await bot.add_cog(PingCog(bot))
