"""Database engine, sessions and the startup tasks."""
import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import settings
from .migrate import migrate

logger = logging.getLogger(__name__)

# The API runs on asyncio, so it always uses the asyncpg driver, whatever the URL says
engine = create_async_engine(
    make_url(settings.database_url).set(drivername="postgresql+asyncpg"),
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """A database session per request. Uncommitted changes are rolled back when it closes."""
    async with async_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def create_initial_admin():
    """Create the admin from INITIAL_ADMIN_*, if those are set and there is no admin yet."""
    from .auth import hash_password
    from .models import User

    name, email, password = (
        settings.initial_admin_name, settings.initial_admin_email, settings.initial_admin_password
    )
    if not (name and email and password):
        return

    email = email.strip().lower()
    async with async_session() as session:
        if (await session.exec(select(User).where(User.is_admin))).first():
            return

        if (await session.exec(select(User).where(User.email == email))).first():
            logger.warning(f"{email} exists but is not an admin, not creating the initial admin")
            return

        session.add(User(
            name=name,
            email=email,
            password_hash=await hash_password(password),
            is_admin=True,
        ))
        await session.commit()
        logger.info(f"Initial admin created: {email}")


async def init_db():
    """Bring the schema up to date and create the initial admin. Runs on application startup."""
    logger.info("Migrating database...")
    # Alembic is synchronous, so it runs in a thread instead of blocking the event loop
    await asyncio.to_thread(migrate)
    await create_initial_admin()
