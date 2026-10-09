"""Password hashing, login tokens and the dependencies that protect the routes."""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import settings
from .database import SessionDep
from .models import User

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"

# Failed logins for one email within LOGIN_LOCK_SECONDS before that email is locked
MAX_FAILED_LOGINS = 5
LOGIN_LOCK_SECONDS = 15 * 60

# Checked when the email is unknown, so a failed login takes as long whether the user exists or not
_DUMMY_HASH = bcrypt.hashpw(b"not a real password", bcrypt.gensalt()).decode()

# email -> times of its recent failed logins. In memory, so a restart clears it.
_failed_logins: dict[str, list[float]] = {}

bearer = HTTPBearer()


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(password: str, password_hash: str) -> bool:
    password_bytes = password.encode()
    # bcrypt only uses 72 bytes and refuses longer passwords
    if len(password_bytes) > 72:
        return False
    return bcrypt.checkpw(password_bytes, password_hash.encode())


# bcrypt is slow on purpose, so it runs in a thread instead of blocking the event loop
async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hash, password)


async def verify_password(password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(_verify, password, password_hash)


def is_login_locked(email: str) -> bool:
    """True after MAX_FAILED_LOGINS failed logins for this email within LOGIN_LOCK_SECONDS."""
    now = time.monotonic()
    for key in list(_failed_logins):
        recent = [t for t in _failed_logins[key] if now - t < LOGIN_LOCK_SECONDS]
        if recent:
            _failed_logins[key] = recent
        else:
            del _failed_logins[key]
    return len(_failed_logins.get(email, [])) >= MAX_FAILED_LOGINS


def record_failed_login(email: str):
    _failed_logins.setdefault(email, []).append(time.monotonic())


def clear_failed_logins(email: str):
    _failed_logins.pop(email, None)


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    """The user with this email and password, or None."""
    user = (await session.exec(select(User).where(User.email == email))).first()
    if user is None:
        await verify_password(password, _DUMMY_HASH)
        return None
    if not await verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user.id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    session: SessionDep,
) -> User:
    """The user the bearer token belongs to."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise invalid

    user = await session.get(User, user_id)
    if user is None:
        raise invalid
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_admin_user(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]
