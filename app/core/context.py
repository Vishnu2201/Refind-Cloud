"""Lightweight application context for managing shared application resources."""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings


@dataclass
class AppContext:
    """Central container holding application configuration and shared resources."""

    settings: Settings
    db_engine: AsyncEngine | None = None
    session_factory: async_sessionmaker[AsyncSession] | None = None
    services: dict[str, Any] = field(default_factory=dict)


_global_app_context: AppContext | None = None


def set_app_context(ctx: AppContext) -> None:
    """Sets the global application context instance."""
    global _global_app_context
    _global_app_context = ctx


def get_app_context() -> AppContext:
    """Retrieves the global application context instance."""
    if _global_app_context is None:
        raise RuntimeError(
            "Application context is uninitialized. Ensure set_app_context is called during startup."
        )
    return _global_app_context


def clear_app_context() -> None:
    """Resets the global application context state. Intended for testing isolation and teardown."""
    global _global_app_context
    _global_app_context = None
