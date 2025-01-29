from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from uuid import UUID, uuid4
from enum import Enum as PyEnum
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.types import Text
from zoneinfo import ZoneInfo


def now_utc() -> datetime:
    return datetime.now(ZoneInfo("UTC"))


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=45, nullable=False, index=True)
    email: str = Field(max_length=255, nullable=False, unique=True, index=True)
    password_hash: str = Field(max_length=255, nullable=False)
    is_admin: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(
        default_factory=now_utc,
        nullable=False,
        sa_column_kwargs={"onupdate": now_utc}
    )

    # Relationships
    received_events: list["Receiver"] = Relationship(back_populates="user")
    gifted_events: list["Receiver"] = Relationship(
        back_populates="gifter",
        sa_relationship_kwargs={"foreign_keys": "[Receiver.gifter_id]"}
    )

    def __repr__(self) -> str:
        return f"User(id={self.id}, name={self.name}, email={self.email})"


class Receiver(SQLModel, table=True):
    __tablename__ = "receivers"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    event_id: UUID = Field(foreign_key="events.id", primary_key=True)
    gifter_id: UUID = Field(foreign_key="users.id", nullable=True, index=True)
    message: Optional[str] = Field(sa_type=Text, nullable=True)
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(
        default_factory=now_utc,
        nullable=False,
        sa_column_kwargs={"onupdate": now_utc}
    )

    # Relationships
    user: User = Relationship(back_populates="received_events", foreign_keys=[user_id])
    event: "Event" = Relationship(back_populates="receivers")
    gifter: Optional[User] = Relationship(back_populates="gifted_events", foreign_keys=[gifter_id])

    def __repr__(self) -> str:
        return f"Receiver(user_id={self.user_id}, event_id={self.event_id})"


class EventStatus(str, PyEnum):
    DRAFT = "draft"
    OPEN = "open"
    ASSIGNED = "assigned"
    CLOSED = "closed"


class EventName(SQLModel, table=True):
    __tablename__ = "event_names"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=45, nullable=False, unique=True, index=True)
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(
        default_factory=now_utc,
        nullable=False,
        sa_column_kwargs={"onupdate": now_utc}
    )

    # Relationships
    events: list["Event"] = Relationship(back_populates="event_name")

    def __repr__(self) -> str:
        return f"EventName(id={self.id}, name={self.name})"


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name_id: UUID = Field(foreign_key="event_names.id", index=True)
    date: datetime = Field(nullable=False, index=True)
    status: EventStatus = Field(
        sa_column=SQLEnum(EventStatus),
        nullable=False,
        default=EventStatus.DRAFT,
        index=True
    )
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(
        default_factory=now_utc,
        nullable=False,
        sa_column_kwargs={"onupdate": now_utc}
    )

    # Relationships
    event_name: EventName = Relationship(back_populates="events")
    receivers: list[Receiver] = Relationship(back_populates="event")

    def __repr__(self) -> str:
        return f"Event(id={self.id}, date={self.date}, status={self.status})"
