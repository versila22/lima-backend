"""Alignments router — grilles d'alignement."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.alignment import Alignment, AlignmentEvent, AlignmentAssignment
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
from app.utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/alignments", tags=["alignments"])


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
    return assignment


@router.delete(
    "/{alignment_id}/assign/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_assignment(
    alignment_id: UUID,
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Remove a player assignment from a grid (admin only)."""
    try:
        await alignment_service.remove_assignment(db, alignment_id, assignment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    return alignment
