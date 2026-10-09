from sqlmodel import SQLModel, Field
from typing import Annotated, Optional
from pydantic import AfterValidator, EmailStr
from datetime import datetime
from datetime import date as date_type
from .models import EventStatus


def _check_password_bytes(password: str) -> str:
    # bcrypt only uses 72 bytes, so longer passwords are refused instead of silently cut off
    if len(password.encode()) > 72:
        raise ValueError("Password is too long")
    return password


# Emails are stored lowercase, so logins don't depend on how someone typed theirs
Email = Annotated[EmailStr, AfterValidator(str.lower)]
Password = Annotated[str, Field(min_length=8), AfterValidator(_check_password_bytes)]


class UserCreate(SQLModel):
    """Model for user creation"""
    name: str = Field(min_length=1, max_length=45)
    email: Email = Field(max_length=45)
    password: Password


class UserResponse(SQLModel):
    """Model for user responses (without sensitive data)"""
    id: int
    name: str
    email: str
    is_admin: bool
    created_at: datetime


class LoginRequest(SQLModel):
    """Model for user login"""
    email: Annotated[str, AfterValidator(lambda email: email.strip().lower())]
    password: str


class UserUpdate(SQLModel):
    """Model for user updates by admin"""
    name: Optional[str] = Field(None, min_length=1, max_length=45)
    email: Optional[Email] = Field(None, max_length=45)
    password: Optional[Password] = None
    is_admin: Optional[bool] = None


class AdminPasswordUpdate(SQLModel):
    """Model for admin updating user passwords (no current password needed)"""
    new_password: Password


class UserProfileUpdate(SQLModel):
    """Model for users updating their own profile"""
    name: Optional[str] = Field(None, min_length=1, max_length=45)
    email: Optional[Email] = Field(None, max_length=45)


class UserPasswordUpdate(SQLModel):
    """Model for users updating their own password"""
    current_password: str
    new_password: Password


class EventCreate(SQLModel):
    """Model for event creation"""
    event_name: str = Field(max_length=45)
    date: date_type


class EventUpdate(SQLModel):
    """Model for event updates"""
    event_name: Optional[str] = Field(None, max_length=45)
    date: Optional[date_type] = None


class EventResponse(SQLModel):
    """Model for event responses"""
    id: int
    event_name: str
    date: date_type
    status: EventStatus
    created_at: datetime
    participant_count: Optional[int] = None
    is_participant: Optional[bool] = None
    has_message: Optional[bool] = None


class EventDetailResponse(EventResponse):
    """Detailed event response with participants"""
    participants: list["ParticipantResponse"] = []


class EventNameCreate(SQLModel):
    """Model for creating event name types"""
    name: str = Field(max_length=45)


class EventNameResponse(SQLModel):
    """Model for event name responses"""
    name: str


class ParticipantJoin(SQLModel):
    """Model for users joining events"""
    event_id: int
    message: Optional[str] = None


class ParticipantUpdate(SQLModel):
    """Model for updating participant message"""
    message: str


class ParticipantResponse(SQLModel):
    """Model for participant responses"""
    user_id: int
    event_id: int
    user_name: str
    message: Optional[str]
    has_message: bool = False
    gifter_name: Optional[str] = None
    is_assigned: bool = False


class AssignmentResponse(SQLModel):
    """Model for showing gift assignments to users"""
    event_id: int
    event_name: str
    event_date: date_type
    event_status: EventStatus
    recipient_name: str
    recipient_message: Optional[str]
    my_message: Optional[str] = None


class Token(SQLModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ManualAssignment(SQLModel):
    """Model for manual Secret Santa assignment"""
    recipient_user_id: int
    gifter_user_id: int


class ManualAssignmentBatch(SQLModel):
    """Model for batch manual assignments"""
    assignments: list[ManualAssignment]


class AdminParticipantMessageUpdate(SQLModel):
    """Model for admin updating participant messages"""
    message: Optional[str] = None


class AssignmentRequest(SQLModel):
    """Model for assignment request with optional history events"""
    history_event_ids: Optional[list[int]] = None
