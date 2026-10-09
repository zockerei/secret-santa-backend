"""Request and response bodies of the API."""
import datetime as dt
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field


def _check_password_bytes(password: str) -> str:
    # bcrypt only uses 72 bytes, so longer passwords are refused instead of silently cut off
    if len(password.encode()) > 72:
        raise ValueError("Password is too long")
    return password


# Emails are stored lowercase, so logins don't depend on how someone typed theirs
Email = Annotated[EmailStr, Field(max_length=255), AfterValidator(str.lower)]
Password = Annotated[str, Field(min_length=8), AfterValidator(_check_password_bytes)]
UserName = Annotated[str, Field(min_length=1, max_length=50)]
EventName = Annotated[str, Field(min_length=1, max_length=100)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Users

class UserResponse(ORMModel):
    id: int
    name: str
    email: str
    is_admin: bool
    created_at: dt.datetime


class LoginRequest(BaseModel):
    email: Annotated[str, AfterValidator(lambda email: email.strip().lower())]
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ProfileUpdate(BaseModel):
    name: UserName | None = None
    email: Email | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: Password


class UserCreate(BaseModel):
    name: UserName
    email: Email
    password: Password
    is_admin: bool = False


class UserUpdate(BaseModel):
    """Admin update of any user. Fields that are left out stay as they are."""
    name: UserName | None = None
    email: Email | None = None
    password: Password | None = None
    is_admin: bool | None = None


# Events, as a participant sees them

class Recipient(BaseModel):
    name: str
    message: str | None


class EventResponse(BaseModel):
    id: int
    name: str
    date: dt.date
    drawn: bool
    participant_count: int
    is_participant: bool
    my_message: str | None
    # Who the user gives a gift to, once the draw is done
    recipient: Recipient | None


class MessageUpdate(BaseModel):
    message: Annotated[str, Field(max_length=10_000)] | None


# Events, as the admin sees them: who takes part, but never the pairs or the messages

class EventCreate(BaseModel):
    name: EventName
    date: dt.date


class EventUpdate(BaseModel):
    name: EventName | None = None
    date: dt.date | None = None


class ParticipantSummary(BaseModel):
    user_id: int
    name: str
    has_message: bool


class AdminEventResponse(BaseModel):
    id: int
    name: str
    date: dt.date
    drawn_at: dt.datetime | None
    created_at: dt.datetime
    participants: list[ParticipantSummary]


class DrawResponse(BaseModel):
    event_id: int
    participant_count: int
    # How many of each participant's previous events were avoided (fewer than 2 if impossible)
    history_events_avoided: int
