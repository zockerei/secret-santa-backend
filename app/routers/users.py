from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
import logging

from ..database import get_session
from ..models import User, Event, Receiver, EventStatus
from ..schemas import (
    EventResponse, ParticipantJoin, ParticipantUpdate,
    AssignmentResponse, UserResponse, UserProfileUpdate, UserPasswordUpdate
)
from ..auth import get_current_user, verify_password, get_password_hash
from ..services.assignment import check_and_update_event_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Returns the current authenticated user's information."
)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
    description="Updates the current authenticated user's name and/or email."
)
async def update_current_user_profile(
    profile_update: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update current user's profile (name and email)"""
    logger.info(f"User {current_user.email} updating their profile")
    
    # Check if at least one field is being updated
    if profile_update.name is None and profile_update.email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (name or email) must be provided"
        )
    
    # Check if email is already taken by another user
    if profile_update.email and profile_update.email != current_user.email:
        email_check_statement = select(User).where(User.email == profile_update.email)
        email_check_result = await session.exec(email_check_statement)
        if email_check_result.first():
            logger.warning(f"Profile update failed: Email {profile_update.email} already in use")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address already in use"
            )
    
    # Update fields
    if profile_update.name is not None:
        current_user.name = profile_update.name
    if profile_update.email is not None:
        current_user.email = profile_update.email
    
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    
    logger.info(f"User profile updated successfully: {current_user.email}")
    return UserResponse.model_validate(current_user)


@router.put(
    "/me/password",
    summary="Update current user password",
    description="Updates the current authenticated user's password."
)
async def update_current_user_password(
    password_update: UserPasswordUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update current user's password"""
    logger.info(f"User {current_user.email} attempting to change password")
    
    # Verify current password
    if not verify_password(password_update.current_password, current_user.password_hash):
        logger.warning(f"Password change failed: incorrect current password for {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Check if new password is different from current
    if verify_password(password_update.new_password, current_user.password_hash):
        logger.warning(f"Password change failed: new password same as current for {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    # Update password
    current_user.password_hash = get_password_hash(password_update.new_password)
    session.add(current_user)
    await session.commit()
    
    logger.info(f"Password updated successfully for user: {current_user.email}")
    return {"message": "Password updated successfully"}


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

        # Check if current user is a participant
        participant_statement = select(Receiver).where(
            Receiver.user_id == current_user.id,
            Receiver.event_id == event.id
        )
        participant_result = await session.exec(participant_statement)
        participant = participant_result.first()

        event_dict = event.model_dump()
        event_dict["participant_count"] = participant_count
        event_dict["is_participant"] = bool(participant)
        event_dict["has_message"] = bool(participant and participant.message) if participant else False
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
    logger.info(f"User {current_user.email} joining event ID: {join_data.event_id}")

    event_statement = select(Event).where(Event.id == join_data.event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        logger.warning(f"Join failed: Event ID {join_data.event_id} not found")
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status not in [EventStatus.DRAFT, EventStatus.OPEN]:
        logger.warning(f"Join failed: Event {event.event_name} status is {event.status}")
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
        logger.warning(f"Join failed: User {current_user.email} already in event ID {join_data.event_id}")
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

    logger.info(f"User {current_user.email} successfully joined event {event.event_name}")
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
    logger.info(f"User {current_user.email} updating message for event ID: {event_id}")

    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        logger.warning(f"Update message failed: Event ID {event_id} not found")
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status == EventStatus.ASSIGNED or event.status == EventStatus.CLOSED:
        logger.warning(f"Update message failed: Event {event.event_name} already assigned/closed")
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
        logger.warning(f"Update message failed: User {current_user.email} not in event ID {event_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not a participant in this event"
        )

    participant.message = message_data.message
    await session.commit()

    await check_and_update_event_status(session, event_id)

    logger.info(f"User {current_user.email} updated message for event {event.event_name}")
    return {"message": "Message updated successfully"}


@router.delete(
    "/events/{event_id}/leave",
    summary="Leave an event",
    description="Remove yourself as a participant from an event (only before assignments)."
)
async def leave_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Leave an event.

    Users can only leave events that haven't been assigned yet.
    Once assignments are made, only admins can remove participants.
    """
    logger.info(f"User {current_user.email} leaving event ID: {event_id}")

    # Verify event exists
    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        logger.warning(f"Leave failed: Event ID {event_id} not found")
        raise HTTPException(status_code=404, detail="Event not found")

    # Check if assignments have been made
    if event.status in [EventStatus.ASSIGNED, EventStatus.CLOSED]:
        logger.warning(f"Leave failed: Event {event.event_name} already assigned/closed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot leave event after assignments have been made. Contact an admin."
        )

    # Find participant record
    participant_statement = select(Receiver).where(
        Receiver.user_id == current_user.id,
        Receiver.event_id == event_id
    )
    participant_result = await session.exec(participant_statement)
    participant = participant_result.first()

    if not participant:
        logger.warning(f"Leave failed: User {current_user.email} not in event ID {event_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not participating in this event"
        )

    # Remove participation
    await session.delete(participant)
    await session.commit()

    await check_and_update_event_status(session, event_id)

    logger.info(f"User {current_user.email} successfully left event {event.event_name}")
    return {
        "message": "Successfully left event",
        "event_id": event_id
    }


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
    logger.info(f"User {current_user.email} fetching their assignments")

    statement = select(Receiver, User, Event).join(
        User, Receiver.user_id == User.id
    ).join(
        Event, Receiver.event_id == Event.id
    ).where(
        Receiver.gifter_id == current_user.id,
        Event.status.in_([EventStatus.ASSIGNED, EventStatus.CLOSED])
    )

    result = await session.exec(statement)
    assignments_data = result.all()

    assignments = []
    for receiver, recipient_user, event in assignments_data:
        # Get the current user's own message for this event
        my_receiver_statement = select(Receiver).where(
            Receiver.user_id == current_user.id,
            Receiver.event_id == event.id
        )
        my_receiver_result = await session.exec(my_receiver_statement)
        my_receiver = my_receiver_result.first()

        assignments.append(AssignmentResponse(
            event_id=event.id,
            event_name=event.event_name,
            event_date=event.date,
            event_status=event.status,
            recipient_name=recipient_user.name,
            recipient_message=receiver.message,
            my_message=my_receiver.message if my_receiver else None
        ))

    logger.info(f"User {current_user.email} has {len(assignments)} assignment(s)")
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

    response = {
        "event_id": event.id,
        "event_name": event.event_name,
        "event_date": event.date,
        "status": event.status,
        "is_participant": bool(participant),
        "has_message": bool(participant and participant.message) if participant else False,
        "message": participant.message if participant else None,
        "can_edit_message": event.status in [EventStatus.DRAFT, EventStatus.OPEN] and bool(participant)
    }

    # Include assignment information for assigned/closed events
    if participant and event.status in [EventStatus.ASSIGNED, EventStatus.CLOSED]:
        assignment_statement = select(Receiver, User).join(
            User, Receiver.user_id == User.id
        ).where(
            Receiver.gifter_id == current_user.id,
            Receiver.event_id == event_id
        )
        assignment_result = await session.exec(assignment_statement)
        assignment_data = assignment_result.first()

        if assignment_data:
            receiver, recipient_user = assignment_data
            response["assignment"] = {
                "recipient_name": recipient_user.name,
                "recipient_message": receiver.message
            }

    return response
