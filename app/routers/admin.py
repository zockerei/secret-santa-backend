"""
Managing users and events.

The admin sees who takes part and whether they wrote a wish list, but never the pairs or
the wish lists themselves, so an admin can take part in the draw like everyone else.
"""
import datetime as dt
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from ..auth import AdminUser, get_admin_user, hash_password
from ..database import SessionDep
from ..draw import draw
from ..models import Event, Participant, User
from ..schemas import (
    AdminEventResponse, DrawResponse, EventCreate, EventUpdate, ParticipantSummary,
    UserCreate, UserResponse, UserUpdate,
)
from .common import get_event, get_participant, get_user, require_not_drawn, require_unused_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(get_admin_user)])


# Users

@router.get("/users", response_model=list[UserResponse], summary="All users")
async def list_users(session: SessionDep):
    return (await session.exec(select(User).order_by(User.name))).all()


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
    description="There is no public registration, the admin creates every account.",
)
async def create_user(new_user: UserCreate, admin: AdminUser, session: SessionDep):
    await require_unused_email(session, new_user.email)
    user = User(
        name=new_user.name,
        email=new_user.email,
        password_hash=await hash_password(new_user.password),
        is_admin=new_user.is_admin,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info(f"Admin {admin.id} created user {user.id} ({user.email})")
    return user


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Change a user",
    description="Name, email, password or admin rights. Fields that are left out stay as they are.",
)
async def update_user(user_id: int, update: UserUpdate, admin: AdminUser, session: SessionDep):
    user = await get_user(session, user_id)
    if user.id == admin.id and update.is_admin is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Du kannst dir die Admin-Rechte nicht selbst entziehen",
        )

    if update.email is not None and update.email != user.email:
        await require_unused_email(session, update.email)
        user.email = update.email
    if update.name is not None:
        user.name = update.name
    if update.password is not None:
        user.password_hash = await hash_password(update.password)
    if update.is_admin is not None:
        user.is_admin = update.is_admin

    await session.commit()
    await session.refresh(user)
    logger.info(f"Admin {admin.id} updated user {user.id}")
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a user")
async def delete_user(user_id: int, admin: AdminUser, session: SessionDep):
    user = await get_user(session, user_id)
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Du kannst dich nicht selbst löschen"
        )

    # Deleting them would leave someone without a gift
    upcoming_drawn = await session.exec(
        select(Event.id)
        .join(Participant, Participant.event_id == Event.id)
        .where(
            Participant.user_id == user_id,
            Event.drawn_at.is_not(None),
            Event.date >= dt.date.today(),
        )
    )
    if upcoming_drawn.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Der Benutzer ist in einer ausgelosten Veranstaltung, erst Auslosung zurücksetzen",
        )

    await session.delete(user)
    await session.commit()
    logger.info(f"Admin {admin.id} deleted user {user_id} ({user.email})")


# Events

async def with_participants(session: SessionDep, events: list[Event]) -> list[AdminEventResponse]:
    """The events with their participants: names and whether they wrote a message, nothing else."""
    rows = await session.exec(
        select(Participant.event_id, User.id, User.name, Participant.message.is_not(None))
        .join(User, User.id == Participant.user_id)
        .where(Participant.event_id.in_([event.id for event in events]))
        .order_by(User.name)
    )
    participants: dict[int, list[ParticipantSummary]] = {event.id: [] for event in events}
    for event_id, user_id, name, has_message in rows:
        participants[event_id].append(
            ParticipantSummary(user_id=user_id, name=name, has_message=has_message)
        )

    return [
        AdminEventResponse(
            id=event.id,
            name=event.name,
            date=event.date,
            drawn_at=event.drawn_at,
            created_at=event.created_at,
            participants=participants[event.id],
        )
        for event in events
    ]


@router.get("/events", response_model=list[AdminEventResponse], summary="All events, newest first")
async def list_events(session: SessionDep):
    events = (await session.exec(select(Event).order_by(Event.date.desc(), Event.id.desc()))).all()
    return await with_participants(session, list(events))


@router.post(
    "/events",
    response_model=AdminEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an event",
)
async def create_event(new_event: EventCreate, admin: AdminUser, session: SessionDep):
    event = Event(name=new_event.name, date=new_event.date)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    logger.info(f"Admin {admin.id} created event {event.id} ({event.name}, {event.date})")
    return (await with_participants(session, [event]))[0]


@router.get("/events/{event_id}", response_model=AdminEventResponse, summary="One event")
async def read_event(event_id: int, session: SessionDep):
    event = await get_event(session, event_id)
    return (await with_participants(session, [event]))[0]


@router.patch("/events/{event_id}", response_model=AdminEventResponse, summary="Change an event")
async def update_event(event_id: int, update: EventUpdate, admin: AdminUser, session: SessionDep):
    event = await get_event(session, event_id)
    if update.name is not None:
        event.name = update.name
    if update.date is not None:
        event.date = update.date

    await session.commit()
    await session.refresh(event)
    logger.info(f"Admin {admin.id} updated event {event_id}")
    return (await with_participants(session, [event]))[0]


@router.delete(
    "/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an event",
    description="Also deletes its pairs, so they no longer count for avoiding repeats.",
)
async def delete_event(event_id: int, admin: AdminUser, session: SessionDep):
    event = await get_event(session, event_id)
    await session.delete(event)
    await session.commit()
    logger.info(f"Admin {admin.id} deleted event {event_id} ({event.name}, {event.date})")


@router.put(
    "/events/{event_id}/participants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Add a user to an event",
)
async def add_participant(event_id: int, user_id: int, admin: AdminUser, session: SessionDep):
    event = await get_event(session, event_id)
    require_not_drawn(event)
    await get_user(session, user_id)
    if await get_participant(session, event_id, user_id) is None:
        session.add(Participant(event_id=event_id, user_id=user_id))
        await session.commit()
        logger.info(f"Admin {admin.id} added user {user_id} to event {event_id}")


@router.delete(
    "/events/{event_id}/participants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a user from an event",
)
async def remove_participant(event_id: int, user_id: int, admin: AdminUser, session: SessionDep):
    event = await get_event(session, event_id)
    require_not_drawn(event)
    participant = await get_participant(session, event_id, user_id)
    if participant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Der Benutzer ist nicht in dieser Veranstaltung",
        )

    await session.delete(participant)
    await session.commit()
    logger.info(f"Admin {admin.id} removed user {user_id} from event {event_id}")


@router.post(
    "/events/{event_id}/draw",
    response_model=DrawResponse,
    summary="Draw who gives a gift to whom",
    description=(
        "Nobody gets someone they had in their last 2 events. If that is impossible, fewer "
        "events are avoided. The result is only shown to each gifter, not to the admin."
    ),
)
async def draw_event(event_id: int, admin: AdminUser, session: SessionDep):
    event = await get_event(session, event_id)
    require_not_drawn(event)
    participants = list(
        (await session.exec(select(Participant).where(Participant.event_id == event_id))).all()
    )
    if len(participants) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zum Auslosen braucht es mindestens 2 Teilnehmer",
        )

    history_events = await draw(session, event, participants)
    logger.info(f"Admin {admin.id} started the draw for event {event_id}")
    return DrawResponse(
        event_id=event_id,
        participant_count=len(participants),
        history_events_avoided=history_events,
    )


@router.delete(
    "/events/{event_id}/draw",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Undo the draw",
    description=(
        "Clears the pairs so people can join or leave again. Not possible once the event is over, "
        "because past pairs are needed to avoid repeats."
    ),
)
async def reset_draw(event_id: int, admin: AdminUser, session: SessionDep):
    event = await get_event(session, event_id)
    if event.drawn_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Die Veranstaltung ist noch nicht ausgelost",
        )
    if event.date < dt.date.today():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Die Veranstaltung ist vorbei"
        )

    participants = await session.exec(select(Participant).where(Participant.event_id == event_id))
    for participant in participants:
        participant.recipient_id = None
    event.drawn_at = None
    await session.commit()
    logger.info(f"Admin {admin.id} reset the draw for event {event_id}")
