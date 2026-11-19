"""
Database configuration and session management.
"""
import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


def _database_url() -> str:
    """Use DATABASE_URL when provided (Render/Postgres), else local SQLite."""
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        return "sqlite+aiosqlite:///./license_reminder.db"
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_pre_ping=not IS_SQLITE,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables and seed default settings."""
    from models import Customer, ImportJob, NotificationLog, AppSettings  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default settings if not present
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(AppSettings))
        settings = result.scalars().first()
        if not settings:
            default_settings = AppSettings(
                reminder_days_before=2,
                timezone="Asia/Kolkata",
                scheduler_enabled=True,
                demo_mode=True,
            )
            session.add(default_settings)
            await session.commit()
