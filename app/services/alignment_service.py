"""Alignment service — business logic for grilles d'alignement."""

import logging
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.alignment import Alignment, AlignmentAssignment, AlignmentEvent
from app.models.event import Event
from app.models.member import Member

logger = logging.getLogger(__name__)


async def get_alignment_with_details(
    db: AsyncSession, alignment_id: UUID
) -> Alignment | None:
    """Load an alignment with its events and assignments eagerly."""
    result = await db.execute(
        select(Alignment)
        .options(
            selectinload(Alignment.alignment_events).selectinload(
                AlignmentEvent.event
            ),
            selectinload(Alignment.assignments),
        )
        .where(Alignment.id == alignment_id)
    )
    return result.scalar_one_or_none()


async def add_events_to_alignment(
    db: AsyncSession,
    alignment: Alignment,
    event_ids: List[UUID],
) -> None:
    """
    Add events to an alignment grid.

    Silently skips events already present.
    Raises ValueError if any event_id does not exist.
    """
    for i, event_id in enumerate(event_ids):
        # Check event exists
        ev_result = await db.execute(select(Event).where(Event.id == event_id))
        if ev_result.scalar_one_or_none() is None:
            raise ValueError(f"Événement {event_id} introuvable")

        # Check not already in alignment
        ae_result = await db.execute(
            select(AlignmentEvent).where(
                AlignmentEvent.alignment_id == alignment.id,
                AlignmentEvent.event_id == event_id,
            )
        )
        if ae_result.scalar_one_or_none() is not None:
            continue

        ae = AlignmentEvent(
            alignment_id=alignment.id,
            event_id=event_id,
            sort_order=i,
        )
        db.add(ae)

    await db.flush()


async def remove_event_from_alignment(
    db: AsyncSession,
    alignment_id: UUID,
    event_id: UUID,
) -> None:
    """
    Remove an event from an alignment and cascade-delete its assignments.

    Raises ValueError if the event is not in the alignment.
    """
    ae_result = await db.execute(
        select(AlignmentEvent).where(
            AlignmentEvent.alignment_id == alignment_id,
            AlignmentEvent.event_id == event_id,
        )
    )
    ae = ae_result.scalar_one_or_none()
    if ae is None:
        raise ValueError("Événement non présent dans cet alignement")

    await db.delete(ae)

    # Delete related assignments
    assignments_result = await db.execute(
        select(AlignmentAssignment).where(
            AlignmentAssignment.alignment_id == alignment_id,
            AlignmentAssignment.event_id == event_id,
        )
    )
    for assignment in assignments_result.scalars().all():
        await db.delete(assignment)

    await db.flush()


async def assign_member(
    db: AsyncSession,
    alignment_id: UUID,
    event_id: UUID,
    member_id: UUID,
    role: str,
) -> AlignmentAssignment:
    """
    Assign a member to an event within an alignment with a given role.

    Raises ValueError if:
      - the member does not exist
      - the event is not in the alignment
      - the member is already assigned to this event
    """
    # Verify event is in alignment
    ae_result = await db.execute(
        select(AlignmentEvent).where(
            AlignmentEvent.alignment_id == alignment_id,
            AlignmentEvent.event_id == event_id,
        )
    )
    if ae_result.scalar_one_or_none() is None:
        raise ValueError("L'événement n'est pas dans cet alignement")

    # Verify member exists
    member_result = await db.execute(select(Member).where(Member.id == member_id))
    if member_result.scalar_one_or_none() is None:
        raise ValueError(f"Membre {member_id} introuvable")

    # Check for duplicate assignment
    dup_result = await db.execute(
        select(AlignmentAssignment).where(
            AlignmentAssignment.alignment_id == alignment_id,
            AlignmentAssignment.event_id == event_id,
            AlignmentAssignment.member_id == member_id,
        )
    )
    if dup_result.scalar_one_or_none() is not None:
        raise ValueError("Ce membre est déjà assigné à cet événement dans cet alignement")

    assignment = AlignmentAssignment(
        alignment_id=alignment_id,
        event_id=event_id,
        member_id=member_id,
        role=role,
    )
    db.add(assignment)
    await db.flush()
    return assignment


async def remove_assignment(
    db: AsyncSession,
    alignment_id: UUID,
    assignment_id: UUID,
) -> None:
    """
    Remove a player assignment from an alignment.

    Raises ValueError if the assignment is not found.
    """
    result = await db.execute(
        select(AlignmentAssignment).where(
            AlignmentAssignment.id == assignment_id,
            AlignmentAssignment.alignment_id == alignment_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise ValueError("Affectation introuvable")
    await db.delete(assignment)
    await db.flush()
