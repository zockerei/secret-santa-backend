import random
from typing import List, Dict, Optional, Set
from sqlmodel import Session, select
import logging

from ..models import Event, Receiver, EventStatus, User

logger = logging.getLogger(__name__)


async def check_and_update_event_status(session: Session, event_id: int) -> bool:
    """
    Check if event status should be updated and update it.
    Only handles DRAFT -> OPEN transition automatically.
    OPEN -> ASSIGNED requires manual admin action.
    Returns True if status was changed.
    """
    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        return False

    participants_statement = select(Receiver).where(Receiver.event_id == event_id)
    participants_result = await session.exec(participants_statement)
    participants = participants_result.all()

    original_status = event.status

    if event.status == EventStatus.DRAFT:
        if len(participants) > 0:
            event.status = EventStatus.OPEN

    if event.status != original_status:
        await session.commit()
        return True

    return False


def _find_valid_assignment(user_ids: List[int], forbidden: Dict[int, Set[int]]) -> Optional[List[int]]:
    """
    Find a valid Secret Santa assignment using backtracking.
    Returns a list where result[i] is the recipient for user_ids[i].
    """
    n = len(user_ids)
    assignment = [-1] * n
    used = [False] * n

    def backtrack(pos: int) -> bool:
        if pos == n:
            return True

        gifter = user_ids[pos]
        forbidden_set = forbidden.get(gifter, set())

        # Try each possible recipient
        indices = list(range(n))
        random.shuffle(indices)  # Randomize to get different valid solutions

        for recipient_idx in indices:
            recipient = user_ids[recipient_idx]

            # Check constraints
            if used[recipient_idx]:
                continue
            if gifter == recipient:  # No self-gifting
                continue
            if recipient in forbidden_set:  # Not in forbidden list
                continue

            # Try this assignment
            assignment[pos] = recipient
            used[recipient_idx] = True

            if backtrack(pos + 1):
                return True

            # Backtrack
            assignment[pos] = -1
            used[recipient_idx] = False

        return False

    if backtrack(0):
        return assignment
    return None


async def assign_secret_santa(
    session: Session,
    event_id: int,
    participants: List[Receiver],
    history_event_ids: Optional[List[int]] = None
) -> bool:
    """
    Assign Secret Santa pairs using an algorithm that avoids recent assignments.
    Each person gives to exactly one person and receives from exactly one person.

    Args:
        session: Database session
        event_id: Current event ID
        participants: List of participants to assign
        history_event_ids: Optional list of event IDs to check for history.
                          If None, uses last 2 events with same event name.
                          If empty list [], no history checking.
    """
    if len(participants) < 2:
        logger.warning(
            f"Cannot assign Secret Santa: insufficient participants ({len(participants)}) for event {event_id}"
        )
        return False

    current_event_statement = select(Event).where(Event.id == event_id)
    current_event_result = await session.exec(current_event_statement)
    current_event = current_event_result.first()

    if not current_event:
        return False

    forbidden_assignments = {}

    # Build forbidden assignments based on history
    if history_event_ids is None:
        # Default behavior: use last 2 events with same event name
        history_statement = select(Event, Receiver).join(
            Receiver, Event.id == Receiver.event_id
        ).where(
            Event.event_name == current_event.event_name,
            Event.id != event_id,
            Event.status == EventStatus.ASSIGNED,
            Receiver.gifter_id.is_not(None)
        ).order_by(Event.created_at.desc())

        history_result = await session.exec(history_statement)
        history_data = history_result.all()

        events_processed = set()
        event_count = 0

        for event, receiver in history_data:
            if event.id not in events_processed:
                events_processed.add(event.id)
                event_count += 1
                if event_count > 2:  # Only consider last 2 events
                    break

            if event_count <= 2:  # Within last 2 events
                gifter_id = receiver.gifter_id
                recipient_id = receiver.user_id

                if gifter_id not in forbidden_assignments:
                    forbidden_assignments[gifter_id] = set()
                forbidden_assignments[gifter_id].add(recipient_id)

    elif len(history_event_ids) > 0:
        # Use specified event IDs for history
        history_statement = select(Receiver).where(
            Receiver.event_id.in_(history_event_ids),
            Receiver.gifter_id.is_not(None)
        )
        history_result = await session.exec(history_statement)
        history_data = history_result.all()

        for receiver in history_data:
            gifter_id = receiver.gifter_id
            recipient_id = receiver.user_id

            if gifter_id not in forbidden_assignments:
                forbidden_assignments[gifter_id] = set()
            forbidden_assignments[gifter_id].add(recipient_id)

    # If history_event_ids is empty list, forbidden_assignments stays empty

    user_ids = [p.user_id for p in participants]

    # Try to find a valid assignment using backtracking
    assignment = _find_valid_assignment(user_ids, forbidden_assignments)

    if assignment is None:
        logger.error(
            f"Could not find valid assignment for event {event_id}. "
            f"Participants: {len(participants)}, Forbidden pairs: {sum(len(v) for v in forbidden_assignments.values())}"
        )
        return False

    # Apply the assignments
    for i, participant in enumerate(participants):
        recipient_id = assignment[i]
        for recipient_participant in participants:
            if recipient_participant.user_id == recipient_id:
                recipient_participant.gifter_id = participant.user_id
                break

    await session.commit()
    logger.info(f"Secret Santa assignments completed for event {event_id} with {len(participants)} participants")
    return True


async def can_modify_event(session: Session, event_id: int) -> bool:
    """Check if an event can be modified (not assigned or closed)"""
    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        return False

    return event.status in [EventStatus.DRAFT, EventStatus.OPEN]


async def get_event_statistics(session: Session, event_id: int) -> Dict:
    """Get event statistics"""
    event_statement = select(Event).where(Event.id == event_id)
    event_result = await session.exec(event_statement)
    event = event_result.first()

    if not event:
        return {}

    participants_statement = select(Receiver).where(Receiver.event_id == event_id)
    participants_result = await session.exec(participants_statement)
    participants = participants_result.all()

    participants_with_messages = [p for p in participants if p.message]
    assigned_participants = [p for p in participants if p.gifter_id is not None]

    return {
        "event_id": event_id,
        "status": event.status,
        "total_participants": len(participants),
        "participants_with_messages": len(participants_with_messages),
        "assigned_participants": len(assigned_participants),
        "participants_without_messages": len(participants) - len(participants_with_messages),
        "can_assign": (
            len(participants) >= 2 and
            event.status == EventStatus.OPEN
        ),
        "ready_for_assignment": (
            len(participants_with_messages) == len(participants) and
            len(participants) >= 2 and
            event.status == EventStatus.OPEN
        )
    }


async def get_assignment_history_info(session: Session, event_id: int) -> Dict:
    """Get assignment history information for the current event"""
    current_event_statement = select(Event).where(Event.id == event_id)
    current_event_result = await session.exec(current_event_statement)
    current_event = current_event_result.first()

    if not current_event:
        return {}

    history_statement = select(Event).where(
        Event.event_name == current_event.event_name,
        Event.id != event_id,
        Event.status == EventStatus.ASSIGNED
    ).order_by(Event.created_at.desc()).limit(2)

    history_result = await session.exec(history_statement)
    previous_events = history_result.all()

    history_info = []
    for event in previous_events:
        assignments_statement = select(Receiver, User).join(
            User, Receiver.user_id == User.id
        ).where(
            Receiver.event_id == event.id,
            Receiver.gifter_id.is_not(None)
        )
        assignments_result = await session.exec(assignments_statement)
        assignments_data = assignments_result.all()

        event_assignments = []
        for receiver, user in assignments_data:
            gifter_statement = select(User).where(User.id == receiver.gifter_id)
            gifter_result = await session.exec(gifter_statement)
            gifter = gifter_result.first()

            event_assignments.append({
                "gifter_name": gifter.name if gifter else "Unknown",
                "recipient_name": user.name
            })

        history_info.append({
            "event_id": event.id,
            "event_date": event.date,
            "assignments": event_assignments
        })

    return {
        "event_name": current_event.event_name,
        "previous_events": history_info,
        "history_count": len(previous_events)
    }
