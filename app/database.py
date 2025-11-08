from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from typing import AsyncGenerator
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
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


async def create_initial_admin():
    """
    Creates an initial admin user if credentials are provided in environment
    variables and no admin exists yet.
    """
    from .models import User
    from .auth import get_password_hash

    if not settings.initial_admin_email or not settings.initial_admin_password:
        logger.info("No initial admin credentials provided, skipping admin creation")
        return

    try:
        async with async_session() as session:
            # Check if any admin already exists
            statement = select(User).where(User.is_admin.is_(True))
            result = await session.exec(statement)
            existing_admin = result.first()

            if existing_admin:
                logger.info(f"Admin user already exists: {existing_admin.email}")
                return

            # Check if user with this email exists
            statement = select(User).where(User.email == settings.initial_admin_email)
            result = await session.exec(statement)
            existing_user = result.first()

            if existing_user:
                logger.warning(
                    f"User with email {settings.initial_admin_email} exists but is not admin. "
                    "Not creating admin account."
                )
                return

            # Create the admin user
            hashed_password = get_password_hash(settings.initial_admin_password)
            admin_user = User(
                name=settings.initial_admin_name,
                email=settings.initial_admin_email,
                password_hash=hashed_password,
                is_admin=True
            )

            session.add(admin_user)
            await session.commit()
            await session.refresh(admin_user)

            logger.info(f"✓ Initial admin user created: {admin_user.email}")

    except Exception as e:
        logger.error(f"Failed to create initial admin user: {e}")
        raise


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

        await create_initial_admin()

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
