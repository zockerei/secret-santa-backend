from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
import sqlalchemy as sa
from sqlalchemy import Index, CheckConstraint
from sqlalchemy.orm import relationship


class EventStatus(str, Enum):
    DRAFT = "Draft"
    OPEN = "Open"
    ASSIGNED = "Assigned"
    CLOSED = "Closed"


class User(SQLModel, table=True):
    """User model with proper constraints and indexes"""
    __tablename__ = "User"
    __table_args__ = (
        Index('idx_user_email', 'email'),
        Index('idx_user_is_admin', 'is_admin'),
        Index('idx_user_created_at', 'created_at'),

        CheckConstraint('length(name) >= 1', name='check_user_name_not_empty'),
        CheckConstraint('length(email) >= 3', name='check_user_email_min_length'),
        CheckConstraint("email LIKE '%@%'", name='check_user_email_format'),
        CheckConstraint('length(password_hash) >= 20', name='check_password_hash_length'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=45, nullable=False)
    password_hash: str = Field(max_length=255, nullable=False)
    email: str = Field(max_length=45, nullable=False, unique=True)
    is_admin: bool = Field(default=False, nullable=False, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    received_assignments: List["Receiver"] = Relationship(
        back_populates="user",
        sa_relationship=relationship(
            "Receiver",
            back_populates="user",
            foreign_keys="[Receiver.user_id]"
        )
    )
    given_assignments: List["Receiver"] = Relationship(
        back_populates="gifter",
        sa_relationship=relationship(
            "Receiver",
            back_populates="gifter",
            foreign_keys="[Receiver.gifter_id]"
        )
    )


class EventName(SQLModel, table=True):
    """Event name lookup table for standardized event types"""
    __tablename__ = "EventName"
    __table_args__ = (
        CheckConstraint('length(name) >= 1', name='check_event_name_not_empty'),
        CheckConstraint('length(name) <= 45', name='check_event_name_max_length'),
    )

    name: str = Field(primary_key=True, max_length=45)

    events: List["Event"] = Relationship(back_populates="event_name_rel")


class Event(SQLModel, table=True):
    """Event model representing Secret Santa events"""
    __tablename__ = "Event"
    __table_args__ = (
        Index('idx_event_name_status', 'event_name', 'status'),
        Index('idx_event_date_status', 'date', 'status'),
        Index('idx_event_created_at', 'created_at'),
        Index('idx_event_status', 'status'),

        CheckConstraint('date >= created_at', name='check_event_date_after_creation'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    event_name: str = Field(
        foreign_key="EventName.name",
        max_length=45,
        nullable=False,
        index=True
    )
    date: datetime = Field(nullable=False, index=True)
    status: EventStatus = Field(default=EventStatus.DRAFT, nullable=False, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    event_name_rel: Optional[EventName] = Relationship(back_populates="events")
    participants: List["Receiver"] = Relationship(back_populates="event")


class Receiver(SQLModel, table=True):
    """Junction table representing participants and their assignments"""
    __tablename__ = "Receiver"
    __table_args__ = (
        Index('idx_receiver_event_user', 'event_id', 'user_id'),
        Index('idx_receiver_event_gifter', 'event_id', 'gifter_id'),
        Index('idx_receiver_gifter', 'gifter_id'),
        Index('idx_receiver_user_message', 'user_id', 'message'),
        Index('idx_receiver_event_message_null', 'event_id',
              sa.text('(message IS NULL)')),

        CheckConstraint('user_id != gifter_id', name='check_no_self_assignment'),
        CheckConstraint('user_id > 0', name='check_user_id_positive'),
        CheckConstraint('event_id > 0', name='check_event_id_positive'),
        CheckConstraint('gifter_id IS NULL OR gifter_id > 0', name='check_gifter_id_positive_or_null'),
    )

    user_id: int = Field(foreign_key="User.id", primary_key=True)
    event_id: int = Field(foreign_key="Event.id", primary_key=True)
    gifter_id: Optional[int] = Field(default=None, foreign_key="User.id", index=True)
    message: Optional[str] = Field(default=None, sa_column=sa.Column(sa.Text))

    user: Optional[User] = Relationship(
        back_populates="received_assignments",
        sa_relationship=relationship(
            "User",
            back_populates="received_assignments",
            foreign_keys="[Receiver.user_id]"
        )
    )
    event: Optional[Event] = Relationship(back_populates="participants")
    gifter: Optional[User] = Relationship(
        back_populates="given_assignments",
        sa_relationship=relationship(
            "User",
            back_populates="given_assignments",
            foreign_keys="[Receiver.gifter_id]"
        )
    )
