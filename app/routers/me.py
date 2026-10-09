import logging

from fastapi import APIRouter, HTTPException, status

from ..auth import CurrentUser, hash_password, verify_password
from ..database import SessionDep
from ..schemas import PasswordChange, ProfileUpdate, UserResponse
from .common import require_unused_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["Me"])


@router.get("", response_model=UserResponse, summary="The logged in user")
async def get_me(user: CurrentUser):
    return user


@router.patch("", response_model=UserResponse, summary="Change your name or email")
async def update_me(update: ProfileUpdate, user: CurrentUser, session: SessionDep):
    if update.email is not None and update.email != user.email:
        await require_unused_email(session, update.email)
        user.email = update.email
    if update.name is not None:
        user.name = update.name

    await session.commit()
    await session.refresh(user)
    logger.info(f"User {user.id} updated their profile")
    return user


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT, summary="Change your password")
async def change_password(change: PasswordChange, user: CurrentUser, session: SessionDep):
    if not await verify_password(change.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is wrong"
        )

    user.password_hash = await hash_password(change.new_password)
    await session.commit()
    logger.info(f"User {user.id} changed their password")
