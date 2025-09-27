from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from typing import AsyncGenerator
from sqlmodel import SQLModel
import logging

from .config import settings


logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

async_session = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.
    Automatically handles session lifecycle.
    """
    async with async_session() as session:
        try:
            logger.debug("Database session created")
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
            logger.debug("Database session closed")


async def init_db():
    """
    Initialize database by creating all tables.
    This runs automatically on application startup.
    """
    try:
        logger.info("Initializing database...")
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

            result = await conn.execute(text("SELECT 1"))
            if result.scalar():
                logger.info("Database initialized successfully")
            else:
                logger.error("Database connection test failed")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
