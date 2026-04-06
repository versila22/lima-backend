"""Alignments router — grilles d'alignement."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.alignment import Alignment, AlignmentAssignment
from app.models.event import Event
from app.models.member import Member
from app.schemas.alignment import (
    AddEventsRequest,
    AlignmentCreate,
    AlignmentDetail,
    AlignmentRead,
    AlignmentUpdate,
    AssignmentRead,
    AssignRequest,
)
from app.services import alignment_service
from app.services.email_service import (
    send_cast_assignment_email,
    send_cast_unassignment_email,
)
from app.utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/alignments", tags=["alignments"])


def _format_event_date(start_at: datetime) -> str:
    return start_at.strftime("%d/%m/%Y à %H:%M")


@router.get("", response_model=List[AlignmentRead])
async def list_alignments(
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """
    List all alignment grids.

    Non-admin users only see published alignments.
    """
    query = select(Alignment).order_by(Alignment.start_date.desc())
    if not current_user.is_admin:
        query = query.where(Alignment.status == "published")
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{alignment_id}", response_model=AlignmentDetail)
async def get_alignment(
    alignment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """Retrieve a full alignment grid with events and assignments."""
    alignment = await alignment_service.get_alignment_with_details(db, alignment_id)
    if alignment is None:
        raise HTTPException(status_code=404, detail="Grille introuvable")
    if alignment.status == "draft" and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Grille non publiée",
        )
    return alignment


@router.post("", response_model=AlignmentRead, status_code=status.HTTP_201_CREATED)
async def create_alignment(
    data: AlignmentCreate,
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(require_admin),
):
    """Create a new alignment grid (admin only)."""
    alignment = Alignment(
        season_id=data.season_id,
        name=data.name,
        start_date=data.start_date,
        end_date=data.end_date,
        created_by=admin.id,
    )
    db.add(alignment)
    await db.flush()
    await db.refresh(alignment)
    return alignment


@router.put("/{alignment_id}", response_model=AlignmentRead)
async def update_alignment(
    alignment_id: UUID,
    data: AlignmentUpdate,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Update alignment name, dates, or status (admin only)."""
    result = await db.execute(
        select(Alignment).where(Alignment.id == alignment_id)
    )
    alignment = result.scalar_one_or_none()
    if alignment is None:
        raise HTTPException(status_code=404, detail="Grille introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(alignment, field, value)
    await db.flush()
    await db.refresh(alignment)
    return alignment


@router.delete("/{alignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alignment(
    alignment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Delete an alignment grid (admin only)."""
    result = await db.execute(
        select(Alignment).where(Alignment.id == alignment_id)
    )
    alignment = result.scalar_one_or_none()
    if alignment is None:
        raise HTTPException(status_code=404, detail="Grille introuvable")
    await db.delete(alignment)
    await db.flush()


@router.post("/{alignment_id}/events", status_code=status.HTTP_200_OK)
async def add_events(
    alignment_id: UUID,
    data: AddEventsRequest,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Add events to a grid (admin only)."""
    result = await db.execute(
        select(Alignment).where(Alignment.id == alignment_id)
    )
    alignment = result.scalar_one_or_none()
    if alignment is None:
        raise HTTPException(status_code=404, detail="Grille introuvable")
    try:
        await alignment_service.add_events_to_alignment(db, alignment, data.event_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"detail": f"{len(data.event_ids)} événement(s) ajouté(s)"}


@router.delete(
    "/{alignment_id}/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_event(
    alignment_id: UUID,
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Remove an event from a grid (admin only)."""
    try:
        await alignment_service.remove_event_from_alignment(db, alignment_id, event_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{alignment_id}/assign",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def assign_member(
    alignment_id: UUID,
    data: AssignRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Assign a player to an event in a grid (admin only)."""
    try:
        assignment = await alignment_service.assign_member(
            db,
            alignment_id=alignment_id,
            event_id=data.event_id,
            member_id=data.member_id,
            role=data.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    member_result = await db.execute(select(Member).where(Member.id == assignment.member_id))
    member = member_result.scalar_one_or_none()

    event_result = await db.execute(select(Event).where(Event.id == assignment.event_id))
    event = event_result.scalar_one_or_none()

    alignment_result = await db.execute(
        select(Alignment).where(Alignment.id == assignment.alignment_id)
    )
    alignment = alignment_result.scalar_one_or_none()

    if member and event and alignment and member.email:
        background_tasks.add_task(
            send_cast_assignment_email,
            to=member.email,
            first_name=member.first_name,
            event_title=event.title,
            event_date=_format_event_date(event.start_at),
            role=assignment.role,
            alignment_name=alignment.name,
            base_url=settings.FRONTEND_URL,
        )

    return assignment


@router.delete(
    "/{alignment_id}/assign/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_assignment(
    alignment_id: UUID,
    assignment_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Remove a player assignment from a grid (admin only)."""
    existing_result = await db.execute(
        select(AlignmentAssignment).where(
            AlignmentAssignment.id == assignment_id,
            AlignmentAssignment.alignment_id == alignment_id,
        )
    )
    assignment = existing_result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=400, detail="Affectation introuvable")

    member_result = await db.execute(select(Member).where(Member.id == assignment.member_id))
    member = member_result.scalar_one_or_none()

    event_result = await db.execute(select(Event).where(Event.id == assignment.event_id))
    event = event_result.scalar_one_or_none()

    alignment_result = await db.execute(
        select(Alignment).where(Alignment.id == assignment.alignment_id)
    )
    alignment = alignment_result.scalar_one_or_none()

    try:
        await alignment_service.remove_assignment(db, alignment_id, assignment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if member and event and alignment and member.email:
        background_tasks.add_task(
            send_cast_unassignment_email,
            to=member.email,
            first_name=member.first_name,
            event_title=event.title,
            event_date=_format_event_date(event.start_at),
            role=assignment.role,
            alignment_name=alignment.name,
            base_url=settings.FRONTEND_URL,
        )


@router.put("/{alignment_id}/publish", response_model=AlignmentRead)
async def publish_alignment(
    alignment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Publish a grid to make it visible to all members (admin only)."""
    result = await db.execute(
        select(Alignment).where(Alignment.id == alignment_id)
    )
    alignment = result.scalar_one_or_none()
    if alignment is None:
        raise HTTPException(status_code=404, detail="Grille introuvable")
    alignment.status = "published"
    await db.flush()
    await db.refresh(alignment)
    return alignment
