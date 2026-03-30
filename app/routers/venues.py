"""Venues router."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.member import Member
from app.models.venue import Venue
from app.schemas.venue import VenueCreate, VenueRead, VenueUpdate
from app.utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("", response_model=List[VenueRead])
async def list_venues(
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """List all venues ordered by name."""
    result = await db.execute(select(Venue).order_by(Venue.name))
    return result.scalars().all()


@router.get("/{venue_id}", response_model=VenueRead)
async def get_venue(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """Retrieve a venue by ID."""
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if venue is None:
        raise HTTPException(status_code=404, detail="Lieu introuvable")
    return venue


@router.post("", response_model=VenueRead, status_code=status.HTTP_201_CREATED)
async def create_venue(
    data: VenueCreate,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Create a new venue (admin only)."""
    venue = Venue(**data.model_dump())
    db.add(venue)
    await db.flush()
    return venue


@router.put("/{venue_id}", response_model=VenueRead)
async def update_venue(
    venue_id: UUID,
    data: VenueUpdate,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Update a venue (admin only)."""
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if venue is None:
        raise HTTPException(status_code=404, detail="Lieu introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(venue, field, value)
    await db.flush()
    return venue
