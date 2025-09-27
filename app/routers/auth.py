from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
import logging

from ..database import get_session
from ..models import User
from ..schemas import UserCreate, UserLogin, Token, UserResponse
from ..auth import (
    authenticate_user,
    create_access_token,
    get_password_hash,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new user account with email and password."
)
async def register(user_data: UserCreate, session: Session = Depends(get_session)):
    logger.info(f"Registration attempt for email: {user_data.email}")

    statement = select(User).where(User.email == user_data.email)
    result = await session.exec(statement)
    if result.first():
        logger.warning(f"Registration failed: email already exists - {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hashed_password
    )

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)

    logger.info(f"User registered successfully: {user_data.email}")
    return UserResponse.model_validate(db_user)


@router.post(
    "/login",
    response_model=Token,
    summary="Login user",
    description="Authenticates user and returns JWT access token."
)
async def login(user_credentials: UserLogin, session: Session = Depends(get_session)):
    logger.info(f"Login attempt for email: {user_credentials.email}")

    user = await authenticate_user(session, user_credentials.email, user_credentials.password)
    if not user:
        logger.warning(f"Login failed for email: {user_credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.id, "email": user.email, "is_admin": user.is_admin},
        expires_delta=access_token_expires
    )

    logger.info(f"Login successful for email: {user_credentials.email}")
    return Token(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )
