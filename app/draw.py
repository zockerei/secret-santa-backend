"""The Secret Santa draw: who gives a gift to whom."""
import logging
import random
from collections import defaultdict

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .models import Event, Participant, utc_now

logger = logging.getLogger(__name__)

# Nobody gets someone they had in their last HISTORY_EVENTS events, if that is possible
HISTORY_EVENTS = 2


def find_assignment(user_ids: list[int], forbidden: dict[int, set[int]]) -> dict[int, int] | None:
    """
    Pick a recipient for every user: nobody gets themselves or someone in their forbidden set,
    and everybody receives exactly one gift. Returns {gifter: recipient}, or None if impossible.

    Randomized backtracking, which is plenty fast for a family sized group.
    """
    if len(user_ids) < 2:
        return None

    assignment: dict[int, int] = {}
    taken: set[int] = set()

    def assign(index: int) -> bool:
        if index == len(user_ids):
            return True
        gifter = user_ids[index]
        not_allowed = taken | forbidden.get(gifter, set()) | {gifter}
        candidates = [user_id for user_id in user_ids if user_id not in not_allowed]
        random.shuffle(candidates)
        for recipient in candidates:
            assignment[gifter] = recipient
            taken.add(recipient)
            if assign(index + 1):
                return True
            taken.remove(recipient)
        assignment.pop(gifter, None)
        return False

    return assignment if assign(0) else None


async def draw(session: AsyncSession, event: Event, participants: list[Participant]) -> int:
    """
    Draw the pairs for an event with at least 2 participants and commit them.

    Recipients from each participant's last HISTORY_EVENTS drawn events are avoided. If that
    is impossible, fewer events are avoided. Returns how many events were avoided.
    """
    user_ids = [participant.user_id for participant in participants]

    # Everyone's previous recipients, newest event first
    rows = await session.exec(
        select(Participant.user_id, Participant.recipient_id)
        .join(Event, Event.id == Participant.event_id)
        .where(
            Participant.user_id.in_(user_ids),
            Participant.recipient_id.is_not(None),
            Event.drawn_at.is_not(None),
            Event.id != event.id,
        )
        .order_by(Event.date.desc(), Event.id.desc())
    )
    previous_recipients: dict[int, list[int]] = defaultdict(list)
    for user_id, recipient_id in rows:
        previous_recipients[user_id].append(recipient_id)

    for history_events in range(HISTORY_EVENTS, -1, -1):
        forbidden = {
            user_id: set(recipients[:history_events])
            for user_id, recipients in previous_recipients.items()
        }
        assignment = find_assignment(user_ids, forbidden)
        if assignment is not None:
            break
        logger.info(f"Event {event.id} can't avoid {history_events} previous events, trying fewer")

    for participant in participants:
        participant.recipient_id = assignment[participant.user_id]
    event.drawn_at = utc_now()
    await session.commit()

    logger.info(
        f"Event {event.id} drawn with {len(participants)} participants, "
        f"avoiding {history_events} previous events"
    )
    return history_events
