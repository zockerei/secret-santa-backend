"""Lookups the routers share."""
from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models import Event, Participant, User


async def get_event(session: AsyncSession, event_id: int) -> Event:
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


async def get_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def get_participant(
    session: AsyncSession, event_id: int, user_id: int
) -> Participant | None:
    return await session.get(Participant, {"event_id": event_id, "user_id": user_id})


def require_not_drawn(event: Event):
    """Joining and leaving is only possible before the draw."""
    if event.drawn_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The draw is already done")


async def require_unused_email(session: AsyncSession, email: str):
    if (await session.exec(select(User).where(User.email == email))).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already in use")
