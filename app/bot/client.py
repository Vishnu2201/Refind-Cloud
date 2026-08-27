"""Custom Discord bot client managing async lifecycle hooks and command synchronization."""

import logging

import discord
from discord.ext import commands

from app.core.context import get_app_context
from app.database.session import check_database_health, close_db_engine, init_db_resources

logger = logging.getLogger(__name__)


class RefindCloudBot(commands.Bot):
    """Refind Cloud production Discord bot client."""

    def __init__(self, guild_id: int | None = None) -> None:
        # Minimum required intents for foundation slash command functionality
        intents = discord.Intents.default()

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
        )
        self.guild_id = guild_id

    async def sync_application_commands(self) -> list[discord.app_commands.AppCommand]:
        """Synchronizes application slash commands globally or to a specific development guild.

        Returns:
            list[discord.app_commands.AppCommand]: List of synchronized application commands.
        """
        if self.guild_id:
            guild_target = discord.Object(id=self.guild_id)
            self.tree.copy_global_to(guild=guild_target)
            synced = await self.tree.sync(guild=guild_target)
            logger.info(
                f"Successfully synced {len(synced)} slash command(s) instantly to Guild ID: {self.guild_id}"
            )
            return synced
        else:
            synced = await self.tree.sync()
            logger.info(
                f"Successfully synced {len(synced)} global slash command(s)."
            )
            return synced

    async def setup_hook(self) -> None:
        """Asynchronous setup hook executed prior to Discord connection establishment."""
        logger.info("Initializing database resources inside Discord event loop...")
        ctx = get_app_context()

        db_engine, session_factory = init_db_resources(
            database_url=ctx.settings.database_url_str,
            echo=(ctx.settings.ENVIRONMENT == "development" and ctx.settings.LOG_LEVEL.upper() == "DEBUG"),
        )
        ctx.db_engine = db_engine
        ctx.session_factory = session_factory

        logger.info("Executing mandatory PostgreSQL connectivity check (SELECT 1)...")
        is_healthy = await check_database_health(db_engine)
        if not is_healthy:
            logger.critical(
                "CRITICAL: Required PostgreSQL database infrastructure is unavailable. "
                "Aborting bot startup sequence. Disposing database resources..."
            )
            await close_db_engine(db_engine)
            raise RuntimeError("PostgreSQL database infrastructure health check failed during bot setup.")

        logger.info("Database health check PASSED: PostgreSQL connection verified.")

        logger.info("Loading foundational cogs...")
        await self.load_extension("app.bot.cogs.ping")
        logger.info("Successfully registered cog: app.bot.cogs.ping")
        await self.load_extension("app.bot.cogs.user")
        logger.info("Successfully registered cog: app.bot.cogs.user")

        # Synchronize slash commands using dedicated reusable method
        await self.sync_application_commands()

    async def on_ready(self) -> None:
        """Event fired when Discord bot successfully connects and authenticates."""
        user_str = str(self.user) if self.user else "Unknown"
        user_id = self.user.id if self.user else 0
        latency_ms = round(self.latency * 1000)

        logger.info(f"Bot connected successfully as {user_str} (ID: {user_id})")
        logger.info(f"Initial websocket latency: {latency_ms}ms")
        logger.info(f"Connected to {len(self.guilds)} Discord guild(s).")

    async def close(self) -> None:
        """Gracefully disposes database resources and closes Discord websocket connections."""
        logger.info("Initiating graceful application shutdown...")
        try:
            await close_db_engine()
        except Exception as exc:
            logger.error(f"Error during database engine shutdown: {exc}")

        await super().close()
        logger.info("Discord gateway connection closed cleanly.")
