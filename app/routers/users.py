from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from ..database import get_session
from ..models import User, Event, Receiver, EventStatus
from ..schemas import (
    EventResponse, ParticipantJoin, ParticipantUpdate,
    AssignmentResponse, UserResponse
)
from ..auth import get_current_user
from ..services.assignment import check_and_update_event_status

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Returns the current authenticated user's information."
)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.get(
    "/events",
    response_model=List[EventResponse],
    summary="Get user events",
    description="Returns events the user can join or is participating in."
)
async def get_available_events(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    joinable_events_statement = select(Event).where(
        Event.status.in_([EventStatus.DRAFT, EventStatus.OPEN])
    )
    joinable_result = await session.exec(joinable_events_statement)
    joinable_events = joinable_result.all()

    participating_events_statement = select(Event).join(Receiver).where(
        Receiver.user_id == current_user.id,
        Event.status.in_([EventStatus.ASSIGNED, EventStatus.CLOSED])
    )
    participating_result = await session.exec(participating_events_statement)
    participating_events = participating_result.all()

    all_events = {event.id: event for event in joinable_events}
    for event in participating_events:
        all_events[event.id] = event

    event_responses = []
    for event in all_events.values():
        count_statement = select(Receiver).where(Receiver.event_id == event.id)
        count_result = await session.exec(count_statement)
        participant_count = len(count_result.all())

        event_dict = event.model_dump()
        event_dict["participant_count"] = participant_count
        event_responses.append(EventResponse(**event_dict))

    event_responses.sort(key=lambda x: x.created_at, reverse=True)

    return event_responses


@router.post(
    "/events/join",
    status_code=status.HTTP_201_CREATED,
    summary="Join an event",
    description="Adds the current user as a participant in the specified event."
)
async def join_event(
    join_data: ParticipantJoin,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Join an event"""
    event_statement = select(Event).where(Event.id == join_data.event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status not in [EventStatus.DRAFT, EventStatus.OPEN]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot join event in current status"
        )

    participant_statement = select(Receiver).where(
        Receiver.user_id == current_user.id,
        Receiver.event_id == join_data.event_id
    )
    participant_result = await session.exec(participant_statement)
    if participant_result.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already joined this event"
        )

    receiver = Receiver(
        user_id=current_user.id,
        event_id=join_data.event_id,
        message=join_data.message
    )

    session.add(receiver)
    await session.commit()

    await check_and_update_event_status(session, join_data.event_id)

    return {"message": "Successfully joined event"}


@router.put(
    "/events/{event_id}/message",
    summary="Update participant message",
    description="Updates the user's message for a specific event."
)
async def update_message(
    event_id: int,
    message_data: ParticipantUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update message for an event (only before assignment)"""
    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status == EventStatus.ASSIGNED or event.status == EventStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change message after assignments are made"
        )

    participant_statement = select(Receiver).where(
        Receiver.user_id == current_user.id,
        Receiver.event_id == event_id
    )
    participant_result = await session.exec(participant_statement)
    participant = participant_result.first()

    if not participant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not a participant in this event"
        )

    participant.message = message_data.message
    await session.commit()

    await check_and_update_event_status(session, event_id)

    return {"message": "Message updated successfully"}


@router.get(
    "/assignments",
    response_model=List[AssignmentResponse],
    summary="Get user assignments",
    description="Returns the user's Secret Santa gift assignments."
)
async def get_my_assignments(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get user's gift assignments"""
    statement = select(Receiver, User, Event).join(
        User, Receiver.user_id == User.id
    ).join(
        Event, Receiver.event_id == Event.id
    ).where(
        Receiver.gifter_id == current_user.id,
        Event.status == EventStatus.ASSIGNED
    )

    result = await session.exec(statement)
    assignments_data = result.all()

    assignments = []
    for receiver, recipient_user, event in assignments_data:
        assignments.append(AssignmentResponse(
            event_id=event.id,
            event_name=event.event_name,
            event_date=event.date,
            recipient_name=recipient_user.name,
            recipient_message=receiver.message
        ))

    return assignments


@router.get(
    "/events/{event_id}/status",
    summary="Get event status",
    description="Returns detailed status information for a specific event."
)
async def get_event_status(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get event status and user's participation info"""
    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    participant_statement = select(Receiver).where(
        Receiver.user_id == current_user.id,
        Receiver.event_id == event_id
    )
    participant_result = await session.exec(participant_statement)
    participant = participant_result.first()

    return {
        "event_id": event.id,
        "event_name": event.event_name,
        "event_date": event.date,
        "status": event.status,
        "is_participant": bool(participant),
        "has_message": bool(participant and participant.message) if participant else False,
        "can_edit_message": event.status in [EventStatus.DRAFT, EventStatus.OPEN] and bool(participant)
    }
