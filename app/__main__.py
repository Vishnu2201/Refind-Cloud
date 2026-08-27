"""Main startup entry point for Refind Cloud Discord bot."""

import logging
import sys

from pydantic import ValidationError

from app.bot.client import RefindCloudBot
from app.core.config import get_settings
from app.core.context import AppContext, set_app_context
from app.core.logging import setup_logging

logger = logging.getLogger("refind_cloud")


def main() -> None:
    """Synchronous main function performing startup initialization and running the bot."""
    # 1. Load and validate environment configuration
    try:
        settings = get_settings()
    except ValidationError as err:
        print("\n==================================================", file=sys.stderr)
        print("CRITICAL: Configuration validation error!", file=sys.stderr)
        print("Required environment variables are missing or invalid:", file=sys.stderr)
        for error in err.errors():
            location = " -> ".join(str(loc) for loc in error["loc"])
            message = error["msg"]
            print(f"  - {location}: {message}", file=sys.stderr)
        print("\nPlease configure your .env file or environment variables.", file=sys.stderr)
        print("==================================================\n", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"CRITICAL: Failed to load application settings: {exc}", file=sys.stderr)
        sys.exit(1)

    # 2. Setup structured logging
    setup_logging(log_level=settings.LOG_LEVEL, environment=settings.ENVIRONMENT)
    logger.info(
        f"Starting Refind Cloud Bot Foundation [Environment: {settings.ENVIRONMENT}, LogLevel: {settings.LOG_LEVEL}]"
    )

    # 3. Register settings in AppContext container
    app_ctx = AppContext(settings=settings)
    set_app_context(app_ctx)

    # 4. Instantiate and run RefindCloudBot
    # Database resources initialization and mandatory health checks are executed in setup_hook()
    # inside Discord's event loop to prevent asyncpg cross-event-loop conflicts.
    bot = RefindCloudBot(guild_id=settings.DISCORD_GUILD_ID)

    try:
        # Pass log_handler=None to prevent discord.py from overwriting our root logger configuration
        bot.run(settings.DISCORD_TOKEN, log_handler=None)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt shutdown signal.")
    except Exception as exc:
        logger.critical(f"Fatal exception during bot execution: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
