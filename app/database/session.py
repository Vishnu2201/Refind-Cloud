"""Async SQLAlchemy session factory and database infrastructure management."""

from collections.abc import AsyncGenerator
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.context import get_app_context

logger = logging.getLogger(__name__)


def init_db_resources(
    database_url: str, echo: bool = False
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Creates and returns a new AsyncEngine and async_sessionmaker pair."""
    engine = create_async_engine(
        database_url,
        echo=echo,
        future=True,
        pool_pre_ping=True,
    )

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    return engine, session_factory


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Retrieves the active database session factory from AppContext."""
    ctx = get_app_context()
    if ctx.session_factory is None:
        raise RuntimeError(
            "Database session factory is uninitialized in AppContext. "
            "Ensure database resources are initialized prior to requesting sessions."
        )
    return ctx.session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an async database session context generator using AppContext session factory."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_database_health(engine: AsyncEngine | None = None) -> bool:
    """Performs a real database connectivity check executing 'SELECT 1'.

    Uses explicit engine if provided, or retrieves active engine from AppContext.
    """
    target_engine = engine
    if target_engine is None:
        try:
            ctx = get_app_context()
            target_engine = ctx.db_engine
        except RuntimeError:
            target_engine = None

    if target_engine is None:
        logger.warning("Database health check called but no active engine is available.")
        return False

    try:
        async with target_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar()
            return value == 1
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}")
        return False


async def close_db_engine(engine: AsyncEngine | None = None) -> None:
    """Gracefully disposes database connection pool resources and clears AppContext references.

    Uses explicit engine if provided, or retrieves active engine from AppContext.
    If AppContext holds a reference to the disposed engine, AppContext references are cleared.
    """
    ctx = None
    try:
        ctx = get_app_context()
    except RuntimeError:
        ctx = None

    target_engine = engine or (ctx.db_engine if ctx else None)

    if target_engine is not None:
        logger.info("Disposing database connection pool resources...")
        await target_engine.dispose()
        if ctx is not None and ctx.db_engine == target_engine:
            ctx.db_engine = None
            ctx.session_factory = None
        logger.info("Database connection pool disposed cleanly.")
