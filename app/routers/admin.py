from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from ..database import get_session
from ..models import User, Event, EventName, Receiver, EventStatus
from ..schemas import (
    UserResponse, UserCreate, UserUpdate,
    EventCreate, EventResponse, EventUpdate, EventDetailResponse,
    EventNameCreate, EventNameResponse,
    ParticipantResponse
)
from ..auth import get_current_admin_user, get_password_hash
from ..services.assignment import (
    check_and_update_event_status,
    get_event_statistics,
    assign_secret_santa,
    get_assignment_history_info
)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="Get all users",
    description="Returns a list of all registered users."
)
async def get_all_users(
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    statement = select(User)
    result = await session.exec(statement)
    users = result.all()
    return [UserResponse.model_validate(user) for user in users]


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Creates a new user account."
)
async def create_user(
    user_data: UserCreate,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    statement = select(User).where(User.email == user_data.email)
    result = await session.exec(statement)
    if result.first():
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

    return UserResponse.model_validate(db_user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Update user (admin only)"""
    statement = select(User).where(User.id == user_id)
    result = await session.exec(statement)
    user = result.first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_data.name is not None:
        user.name = user_data.name
    if user_data.email is not None:
        email_check = select(User).where(User.email == user_data.email, User.id != user_id)
        email_result = await session.exec(email_check)
        if email_result.first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        user.email = user_data.email
    if user_data.password is not None:
        user.password_hash = get_password_hash(user_data.password)
    if user_data.is_admin is not None:
        user.is_admin = user_data.is_admin

    await session.commit()
    await session.refresh(user)

    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Delete user (admin only)"""
    statement = select(User).where(User.id == user_id)
    result = await session.exec(statement)
    user = result.first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await session.delete(user)
    await session.commit()

    return {"message": "User deleted successfully"}


@router.get(
    "/events",
    response_model=List[EventResponse],
    summary="Get all events",
    description="Returns all events with participant counts."
)
async def get_all_events(
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    statement = select(
        Event,
        func.count(Receiver.user_id).label("participant_count")
    ).outerjoin(Receiver).group_by(Event.id)

    result = await session.exec(statement)
    events_data = result.all()

    events = []
    for event, participant_count in events_data:
        event_dict = event.model_dump()
        event_dict["participant_count"] = participant_count or 0
        events.append(EventResponse(**event_dict))

    return events


@router.get(
    "/events/{event_id}",
    response_model=EventDetailResponse,
    summary="Get event details",
    description="Returns detailed event information including participants."
)
async def get_event_detail(
    event_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    participants_statement = select(Receiver, User).join(User).where(Receiver.event_id == event_id)
    participants_result = await session.exec(participants_statement)
    participants_data = participants_result.all()

    participants = []
    for receiver, user in participants_data:
        gifter_name = None
        if receiver.gifter_id:
            gifter_statement = select(User).where(User.id == receiver.gifter_id)
            gifter_result = await session.exec(gifter_statement)
            gifter = gifter_result.first()
            gifter_name = gifter.name if gifter else None

        participants.append(ParticipantResponse(
            user_id=user.id,
            event_id=event_id,
            user_name=user.name,
            message=receiver.message,
            has_message=bool(receiver.message),
            gifter_name=gifter_name,
            is_assigned=bool(receiver.gifter_id)
        ))

    event_dict = event.model_dump()
    event_dict["participant_count"] = len(participants)
    event_dict["participants"] = participants

    return EventDetailResponse(**event_dict)


@router.post(
    "/events",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create event",
    description="Creates a new Secret Santa event."
)
async def create_event(
    event_data: EventCreate,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    name_statement = select(EventName).where(EventName.name == event_data.event_name)
    name_result = await session.exec(name_statement)
    if not name_result.first():
        event_name = EventName(name=event_data.event_name)
        session.add(event_name)

    db_event = Event(
        event_name=event_data.event_name,
        date=event_data.date
    )

    session.add(db_event)
    await session.commit()
    await session.refresh(db_event)

    event_dict = db_event.model_dump()
    event_dict["participant_count"] = 0

    return EventResponse(**event_dict)


@router.put("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    event_data: EventUpdate,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Update event (admin only)"""
    statement = select(Event).where(Event.id == event_id)
    result = await session.exec(statement)
    event = result.first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event_data.event_name is not None:
        name_statement = select(EventName).where(EventName.name == event_data.event_name)
        name_result = await session.exec(name_statement)
        if not name_result.first():
            event_name = EventName(name=event_data.event_name)
            session.add(event_name)
        event.event_name = event_data.event_name

    if event_data.date is not None:
        event.date = event_data.date

    await session.commit()
    await session.refresh(event)

    count_statement = select(func.count(Receiver.user_id)).where(Receiver.event_id == event_id)
    count_result = await session.exec(count_statement)
    participant_count = count_result.first() or 0

    event_dict = event.model_dump()
    event_dict["participant_count"] = participant_count

    return EventResponse(**event_dict)


@router.delete(
    "/events/{event_id}",
    summary="Delete event",
    description="Permanently deletes an event and all its data."
)
async def delete_event(
    event_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    statement = select(Event).where(Event.id == event_id)
    result = await session.exec(statement)
    event = result.first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    await session.delete(event)
    await session.commit()

    return {"message": "Event deleted successfully"}


@router.get("/event-names", response_model=List[EventNameResponse])
async def get_event_names(
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Get all event names (admin only)"""
    statement = select(EventName)
    result = await session.exec(statement)
    event_names = result.all()
    return [EventNameResponse.model_validate(name) for name in event_names]


@router.post("/event-names", response_model=EventNameResponse)
async def create_event_name(
    event_name_data: EventNameCreate,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Create a new event name type (admin only)"""
    statement = select(EventName).where(EventName.name == event_name_data.name)
    result = await session.exec(statement)
    if result.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event name already exists"
        )

    event_name = EventName(name=event_name_data.name)
    session.add(event_name)
    await session.commit()
    await session.refresh(event_name)

    return EventNameResponse.model_validate(event_name)


@router.post(
    "/events/{event_id}/assign",
    summary="Assign Secret Santa pairs",
    description="Manually triggers Secret Santa assignment for an event."
)
async def assign_event(
    event_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    participants_statement = select(Receiver).where(Receiver.event_id == event_id)
    participants_result = await session.exec(participants_statement)
    participants = participants_result.all()

    if len(participants) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Need at least 2 participants to assign"
        )

    success = await assign_secret_santa(session, event_id, participants)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign Secret Santa pairs"
        )

    event.status = EventStatus.ASSIGNED
    await session.commit()

    return {
        "message": "Secret Santa pairs assigned successfully",
        "event_id": event_id,
        "participants_assigned": len(participants)
    }


@router.post("/events/{event_id}/close")
async def close_event(
    event_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Close an event (admin only)"""
    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    event.status = EventStatus.CLOSED
    await session.commit()

    return {"message": "Event closed successfully"}


@router.post("/events/{event_id}/reopen")
async def reopen_event(
    event_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Reopen a closed event (admin only)"""
    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status == EventStatus.CLOSED:
        event.status = EventStatus.ASSIGNED  # or OPEN depending on if assignments exist
        assignments_statement = select(Receiver).where(
            Receiver.event_id == event_id,
            Receiver.gifter_id.is_not(None)
        )
        assignments_result = await session.exec(assignments_statement)
        assignments = assignments_result.all()

        if not assignments:
            event.status = EventStatus.OPEN

        await session.commit()

    return {"message": "Event reopened successfully"}


@router.get("/events/{event_id}/statistics")
async def get_event_stats(
    event_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Get detailed event statistics (admin only)"""
    statistics = await get_event_statistics(session, event_id)

    if not statistics:
        raise HTTPException(status_code=404, detail="Event not found")

    return statistics


@router.get("/events/{event_id}/history")
async def get_assignment_history(
    event_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Get assignment history for this event name (admin only)"""
    history = await get_assignment_history_info(session, event_id)

    if not history:
        raise HTTPException(status_code=404, detail="Event not found")

    return history


@router.get(
    "/events/{event_id}/participants-without-messages",
    summary="Get participants without messages",
    description="Returns participants who haven't written their messages yet."
)
async def get_participants_without_messages(
    event_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    participants_statement = select(Receiver, User).join(User).where(
        Receiver.event_id == event_id,
        Receiver.message.is_(None)
    )
    participants_result = await session.exec(participants_statement)
    participants_data = participants_result.all()

    participants_without_messages = []
    for receiver, user in participants_data:
        participants_without_messages.append({
            "user_id": user.id,
            "user_name": user.name,
            "email": user.email
        })

    return {
        "event_id": event_id,
        "participants_without_messages": participants_without_messages,
        "count": len(participants_without_messages)
    }


@router.post(
    "/events/{event_id}/add-participant",
    status_code=status.HTTP_201_CREATED,
    summary="Add participant to event",
    description="Adds a user as a participant to the specified event."
)
async def add_participant_to_event(
    event_id: int,
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    user_statement = select(User).where(User.id == user_id)
    user_result = await session.exec(user_statement)
    user = user_result.first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    participant_statement = select(Receiver).where(
        Receiver.user_id == user_id,
        Receiver.event_id == event_id
    )
    participant_result = await session.exec(participant_statement)
    if participant_result.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already participating in this event"
        )

    receiver = Receiver(
        user_id=user_id,
        event_id=event_id
    )

    session.add(receiver)
    await session.commit()

    await check_and_update_event_status(session, event_id)

    return {
        "message": f"User {user.name} added to event successfully",
        "user_id": user_id,
        "event_id": event_id
    }


@router.delete("/events/{event_id}/participants/{user_id}")
async def remove_participant_from_event(
    event_id: int,
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Remove a user from an event (admin only)"""
    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status in [EventStatus.ASSIGNED, EventStatus.CLOSED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove participants from assigned or closed events"
        )

    participant_statement = select(Receiver).where(
        Receiver.user_id == user_id,
        Receiver.event_id == event_id
    )
    participant_result = await session.exec(participant_statement)
    participant = participant_result.first()

    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not participating in this event"
        )

    await session.delete(participant)
    await session.commit()

    return {"message": "Participant removed successfully"}
