from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from datetime import date as date_type
from .models import EventStatus


class UserCreate(SQLModel):
    """Model for user creation"""
    name: str = Field(max_length=45)
    email: str = Field(max_length=45)
    password: str = Field(min_length=8)


class UserResponse(SQLModel):
    """Model for user responses (without sensitive data)"""
    id: int
    name: str
    email: str
    is_admin: bool
    created_at: datetime


class UserLogin(SQLModel):
    """Model for user login"""
    email: str
    password: str


class UserUpdate(SQLModel):
    """Model for user updates by admin"""
    name: Optional[str] = Field(None, max_length=45)
    email: Optional[str] = Field(None, max_length=45)
    password: Optional[str] = Field(None, min_length=8)
    is_admin: Optional[bool] = None


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


class TokenData(SQLModel):
    """Token payload data"""
    user_id: Optional[int] = None
    email: Optional[str] = None
    is_admin: bool = False


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
