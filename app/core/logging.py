"""Structured application logging setup."""

import datetime
import json
import logging
import sys
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter for production environments."""

    def __init__(self, environment: str = "production") -> None:
        super().__init__()
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "environment": self.environment,
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Collect explicit contextual fields attached to log records
        context_keys = (
            "interaction_id",
            "guild_id",
            "user_id",
            "channel_id",
            "order_id",
            "service_id",
            "request_id",
            "correlation_id",
        )
        context: Dict[str, Any] = {}
        for key in context_keys:
            if hasattr(record, key):
                context[key] = getattr(record, key)

        if hasattr(record, "extra_context") and isinstance(record.extra_context, dict):
            context.update(record.extra_context)

        if context:
            log_record["context"] = context

        return json.dumps(log_record)


class DevelopmentFormatter(logging.Formatter):
    """Human-readable formatter for local development environments."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.datetime.fromtimestamp(record.created).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        output = f"[{timestamp}] [{record.levelname:<8}] [{record.name}]: {record.getMessage()}"

        context_keys = (
            "interaction_id",
            "guild_id",
            "user_id",
            "channel_id",
            "order_id",
            "service_id",
            "request_id",
            "correlation_id",
        )
        extras = []
        for key in context_keys:
            if hasattr(record, key):
                extras.append(f"{key}={getattr(record, key)}")

        if hasattr(record, "extra_context") and isinstance(record.extra_context, dict):
            for k, v in record.extra_context.items():
                extras.append(f"{k}={v}")

        if extras:
            output += f" | {', '.join(extras)}"

        if record.exc_info:
            output += f"\n{self.formatException(record.exc_info)}"

        return output


class ContextualLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter for enriching logs with contextual metadata."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        extra = kwargs.setdefault("extra", {})
        if self.extra:
            extra.update(self.extra)
        return msg, kwargs


def setup_logging(log_level: str = "INFO", environment: str = "production") -> None:
    """Configures root application logging based on environment and level."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers to prevent duplicate log outputs
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    if environment.lower() == "development":
        console_handler.setFormatter(DevelopmentFormatter())
    else:
        console_handler.setFormatter(JSONFormatter(environment=environment))

    root_logger.addHandler(console_handler)

    # Reduce noisy loggers from third-party libraries
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str, **context: Any) -> logging.LoggerAdapter:
    """Returns a logger adapter pre-configured with contextual fields."""
    logger = logging.getLogger(name)
    return ContextualLoggerAdapter(logger, extra=context)
