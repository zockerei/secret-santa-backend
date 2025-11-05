"""
Create admin user script for Secret Santa API.
Run this once to create your initial admin account.

Usage:
  python create_admin.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.models import User
from app.auth import get_password_hash
from app.config import settings


async def create_admin():
    """Create an admin user interactively."""
    print("=" * 50)
    print("Secret Santa API - Create Admin User")
    print("=" * 50)
    print()

    # Get user input
    name = input("Admin name: ").strip()
    email = input("Admin email: ").strip()
    password = input("Admin password (paste enabled): ").strip()
    password_confirm = input("Confirm password: ").strip()

    # Validate input
    if not name or not email or not password:
        print("❌ All fields are required!")
        return

    if password != password_confirm:
        print("❌ Passwords don't match!")
        return

    if len(password) < 8:
        print("❌ Password must be at least 8 characters!")
        return

    # Create database connection
    engine = create_async_engine(settings.database_url)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        # Check if user already exists
        statement = select(User).where(User.email == email)
        result = await session.exec(statement)
        existing_user = result.first()

        if existing_user:
            print(f"❌ User with email '{email}' already exists!")

            # Offer to make them admin if they aren't
            if not existing_user.is_admin:
                make_admin = input("Make this user an admin? (y/n): ").lower()
                if make_admin == 'y':
                    existing_user.is_admin = True
                    await session.commit()
                    print(f"✅ User '{existing_user.name}' is now an admin!")
            else:
                print(f"ℹ️  User '{existing_user.name}' is already an admin.")
            return

        # Create new admin user
        hashed_password = get_password_hash(password)
        admin_user = User(
            name=name,
            email=email,
            password_hash=hashed_password,
            is_admin=True
        )

        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)

        print("\n" + "=" * 50)
        print("✅ Admin user created successfully!")
        print("=" * 50)
        print(f"Name:     {admin_user.name}")
        print(f"Email:    {admin_user.email}")
        print(f"Admin:    {admin_user.is_admin}")
        print(f"ID:       {admin_user.id}")
        print("=" * 50)
        print("\nYou can now log in with these credentials.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_admin())
