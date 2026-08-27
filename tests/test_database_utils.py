"""Unit tests for database infrastructure utility functions."""

import pytest

from app.core.context import AppContext, clear_app_context, get_app_context, set_app_context
from app.core.logging import DevelopmentFormatter, JSONFormatter
from app.database.session import check_database_health, close_db_engine


@pytest.mark.asyncio
async def test_database_health_check_returns_false_when_uninitialized() -> None:
    """Verifies that check_database_health handles uninitialized AppContext and engine=None safely."""
    clear_app_context()
    result = await check_database_health(engine=None)
    assert result is False


def test_app_context_initialization_and_clearing() -> None:
    """Verifies AppContext container setter, getter, and clear_app_context behavior."""
    from app.core.config import get_settings

    clear_app_context()
    with pytest.raises(RuntimeError) as exc_info:
        get_app_context()
    assert "Application context is uninitialized" in str(exc_info.value)

    settings = get_settings()
    ctx = AppContext(settings=settings)
    set_app_context(ctx)

    retrieved = get_app_context()
    assert retrieved.settings == settings
    assert retrieved.db_engine is None
    assert retrieved.session_factory is None

    clear_app_context()
    with pytest.raises(RuntimeError):
        get_app_context()


@pytest.mark.asyncio
async def test_close_db_engine_clears_app_context_references() -> None:
    """Verifies close_db_engine clears AppContext db_engine and session_factory references."""
    from app.core.config import get_settings

    settings = get_settings()
    ctx = AppContext(settings=settings, db_engine=None, session_factory=None)
    set_app_context(ctx)

    # Calling close_db_engine when db_engine is None should complete cleanly without errors
    await close_db_engine(engine=None)
    assert ctx.db_engine is None
    assert ctx.session_factory is None


def test_json_logging_formatter() -> None:
    """Verifies production JSON log formatting includes required keys."""
    import logging

    formatter = JSONFormatter(environment="production")
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test log message",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert '"message": "Test log message"' in formatted
    assert '"level": "INFO"' in formatted
    assert '"environment": "production"' in formatted


def test_dev_logging_formatter() -> None:
    """Verifies development log formatting outputs human-readable strings."""
    import logging

    formatter = DevelopmentFormatter()
    record = logging.LogRecord(
        name="dev_logger",
        level=logging.WARNING,
        pathname="test.py",
        lineno=20,
        msg="Dev warning message",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert "WARNING" in formatted
    assert "Dev warning message" in formatted
