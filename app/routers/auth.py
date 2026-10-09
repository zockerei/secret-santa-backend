import logging

from fastapi import APIRouter, HTTPException, status

from ..auth import (
    authenticate, clear_failed_logins, create_access_token, is_login_locked, record_failed_login
)
from ..database import SessionDep
from ..schemas import LoginRequest, Token, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token, summary="Log in and get an access token")
async def login(credentials: LoginRequest, session: SessionDep):
    email = credentials.email
    if is_login_locked(email):
        logger.warning(f"Login blocked, too many failed attempts: {email}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed logins, try again in 15 minutes",
        )

    user = await authenticate(session, email, credentials.password)
    if user is None:
        record_failed_login(email)
        logger.warning(f"Failed login: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clear_failed_logins(email)
    logger.info(f"Login: {email}")
    return Token(access_token=create_access_token(user), user=UserResponse.model_validate(user))
