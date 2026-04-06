"""Events router."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alignment import AlignmentAssignment, AlignmentEvent
from app.models.event import Event
from app.models.member import Member
from app.models.show_plan import ShowPlan
from app.schemas.event import (
    CalendarImportReport,
    EventCreate,
    EventRead,
    EventUpdate,
)
from app.services import import_service
from app.utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/events", tags=["events"])


class EventCastMember(BaseModel):
    member_id: UUID
    first_name: str
    last_name: str
    role: str


@router.get("", response_model=List[EventRead])
async def list_events(
    season_id: Optional[UUID] = Query(None),
    event_type: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """
    List events with optional filters.

    Non-admin users cannot see events with visibility='admin'.
    """
    query = select(Event)
    if season_id:
        query = query.where(Event.season_id == season_id)
    if event_type:
        query = query.where(Event.event_type == event_type)
    if from_date:
        query = query.where(Event.start_at >= from_date)
    if to_date:
        query = query.where(Event.start_at <= to_date)
    if not current_user.is_admin:
        query = query.where(Event.visibility != "admin")

    query = query.order_by(Event.start_at)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{event_id}", response_model=EventRead)
async def get_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """Retrieve an event by ID."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Événement introuvable")
    if event.visibility == "admin" and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Accès refusé")
    return event


@router.get("/{event_id}/cast", response_model=List[EventCastMember])
async def get_event_cast(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """Return the cast assignments for a given event."""
    event_result = await db.execute(select(Event.id).where(Event.id == event_id))
    if event_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Événement introuvable")

    result = await db.execute(
        select(
            AlignmentAssignment.member_id,
            Member.first_name,
            Member.last_name,
            AlignmentAssignment.role,
        )
        .join(Member, Member.id == AlignmentAssignment.member_id)
        .where(AlignmentAssignment.event_id == event_id)
        .order_by(AlignmentAssignment.role, Member.last_name, Member.first_name)
    )
    return [
        EventCastMember(
            member_id=member_id,
            first_name=first_name,
            last_name=last_name,
            role=role,
        )
        for member_id, first_name, last_name, role in result.all()
    ]


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Create a new event (admin only)."""
    event = Event(**data.model_dump())
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


@router.put("/{event_id}", response_model=EventRead)
async def update_event(
    event_id: UUID,
    data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Update an event (admin only)."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Événement introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    await db.flush()
    await db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Delete an event (admin only)."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Événement introuvable")
    await db.execute(
        delete(AlignmentAssignment).where(AlignmentAssignment.event_id == event_id)
    )
    await db.execute(delete(AlignmentEvent).where(AlignmentEvent.event_id == event_id))
    await db.execute(delete(ShowPlan).where(ShowPlan.event_id == event_id))
    await db.delete(event)
    await db.flush()


@router.post("/import-calendar", response_model=CalendarImportReport)
async def import_calendar(
    season_id: UUID = Query(..., description="Saison cible"),
    file: UploadFile = File(..., description="Fichier Excel du calendrier"),
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """
    Import events from an Excel calendar file (admin only).

    Detects event types from title keywords. Skips duplicate entries.
    """
    excel_bytes = await file.read()
    report = await import_service.import_excel_calendar(db, excel_bytes, season_id)
    return report
