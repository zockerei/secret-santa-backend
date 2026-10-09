"""
The database tables. A change here needs a migration, see "Database and Migrations" in the README.
"""
import datetime as dt

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=50)
    # Stored lowercase, see schemas.Email
    email: str = Field(max_length=255, unique=True)
    password_hash: str = Field(max_length=255)
    is_admin: bool = False
    created_at: dt.datetime = Field(default_factory=utc_now, sa_type=sa.DateTime(timezone=True))


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    date: dt.date
    # Set by the draw. Until then people can join and leave.
    drawn_at: dt.datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    created_at: dt.datetime = Field(default_factory=utc_now, sa_type=sa.DateTime(timezone=True))


class Participant(SQLModel, table=True):
    """A user taking part in an event, with their wish list and who they give a gift to."""

    __tablename__ = "participants"
    __table_args__ = (
        # Everybody receives exactly one gift (several NULLs are fine before the draw)
        sa.UniqueConstraint("event_id", "recipient_id", name="uq_participants_event_recipient"),
        sa.CheckConstraint("recipient_id <> user_id", name="ck_participants_not_self"),
    )

    user_id: int = Field(foreign_key="users.id", primary_key=True, index=True, ondelete="CASCADE")
    event_id: int = Field(foreign_key="events.id", primary_key=True, ondelete="CASCADE")
    message: str | None = Field(default=None, sa_type=sa.Text)
    # Who this participant gives a gift to, set by the draw
    recipient_id: int | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
