"""Events as a participant sees them: joining, the wish list and who to give a gift to."""
import datetime as dt
import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import aliased
from sqlmodel import select

from ..auth import CurrentUser
from ..database import SessionDep
from ..models import Event, Participant, User
from ..schemas import EventResponse, MessageUpdate, Recipient
from .common import get_event, get_participant, require_not_drawn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["Events"])


@router.get(
    "",
    response_model=list[EventResponse],
    summary="Events you can join or take part in",
    description="Includes who you give a gift to, and their wish list, once the draw is done.",
)
async def list_events(user: CurrentUser, session: SessionDep):
    mine = aliased(Participant)
    recipient_row = aliased(Participant)
    recipient_user = aliased(User)
    counts = (
        select(Participant.event_id, func.count().label("count"))
        .group_by(Participant.event_id)
        .subquery()
    )

    rows = await session.exec(
        select(
            Event,
            func.coalesce(counts.c.count, 0),
            mine.user_id,
            mine.message,
            recipient_user.name,
            recipient_row.message,
        )
        .outerjoin(counts, counts.c.event_id == Event.id)
        .outerjoin(mine, and_(mine.event_id == Event.id, mine.user_id == user.id))
        .outerjoin(recipient_user, recipient_user.id == mine.recipient_id)
        .outerjoin(
            recipient_row,
            and_(recipient_row.event_id == Event.id, recipient_row.user_id == mine.recipient_id),
        )
        # Events that are still open to join, and every event the user is in
        .where(or_(Event.drawn_at.is_(None), mine.user_id.is_not(None)))
        .order_by(Event.date.desc(), Event.id.desc())
    )

    return [
        EventResponse(
            id=event.id,
            name=event.name,
            date=event.date,
            drawn=event.drawn_at is not None,
            participant_count=count,
            is_participant=my_user_id is not None,
            my_message=my_message,
            recipient=(
                Recipient(name=recipient_name, message=recipient_message)
                if recipient_name else None
            ),
        )
        for event, count, my_user_id, my_message, recipient_name, recipient_message in rows
    ]


@router.post("/{event_id}/join", status_code=status.HTTP_204_NO_CONTENT, summary="Join an event")
async def join_event(event_id: int, user: CurrentUser, session: SessionDep):
    event = await get_event(session, event_id)
    require_not_drawn(event)
    if await get_participant(session, event_id, user.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Du bist schon dabei"
        )

    session.add(Participant(event_id=event_id, user_id=user.id))
    await session.commit()
    logger.info(f"User {user.id} joined event {event_id}")


@router.delete("/{event_id}/join", status_code=status.HTTP_204_NO_CONTENT, summary="Leave an event")
async def leave_event(event_id: int, user: CurrentUser, session: SessionDep):
    event = await get_event(session, event_id)
    require_not_drawn(event)
    participant = await get_participant(session, event_id, user.id)
    if participant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Du bist nicht in dieser Veranstaltung"
        )

    await session.delete(participant)
    await session.commit()
    logger.info(f"User {user.id} left event {event_id}")


@router.put(
    "/{event_id}/message",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Write your wish list",
    description="Possible until the event day, so your Secret Santa always sees the latest one.",
)
async def update_message(
    event_id: int, update: MessageUpdate, user: CurrentUser, session: SessionDep
):
    event = await get_event(session, event_id)
    if event.date < dt.date.today():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Die Veranstaltung ist vorbei"
        )
    participant = await get_participant(session, event_id, user.id)
    if participant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Du bist nicht in dieser Veranstaltung"
        )

    participant.message = update.message or None
    await session.commit()
    logger.info(f"User {user.id} updated their message for event {event_id}")
