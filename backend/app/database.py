# =============================================================================
# EX-DIGITAL — Async Database Engine & Session Management
# =============================================================================
# Uses SQLAlchemy 2.0 async engine with asyncpg driver.
# Provides get_db() as a FastAPI dependency for per-request sessions.
# =============================================================================

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Engine — created once per process; the pool is shared across requests.
# ---------------------------------------------------------------------------
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,          # Log SQL in debug mode only
    pool_size=10,                  # Connections kept open in the pool
    max_overflow=20,               # Extra connections allowed above pool_size
    pool_pre_ping=True,            # Test connections before using them
    pool_recycle=3600,             # Recycle connections every hour
)

# ---------------------------------------------------------------------------
# Session factory — expire_on_commit=False keeps objects usable after commit.
# ---------------------------------------------------------------------------
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Declarative base — all ORM models inherit from this.
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# ---------------------------------------------------------------------------
# Dependency injection helper — used in FastAPI route signatures.
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that yields a database session per request.
    Automatically rolls back on exception and closes the session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
