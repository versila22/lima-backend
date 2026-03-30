"""Seasons router."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.member import Member
from app.models.season import Season
from app.schemas.season import SeasonCreate, SeasonRead, SeasonUpdate
from app.utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/seasons", tags=["seasons"])


@router.get("", response_model=List[SeasonRead])
async def list_seasons(
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """List all seasons ordered by start date (newest first)."""
    result = await db.execute(select(Season).order_by(Season.start_date.desc()))
    return result.scalars().all()


@router.get("/current", response_model=SeasonRead)
async def get_current_season(
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """Return the season marked as current."""
    result = await db.execute(select(Season).where(Season.is_current == True))
    season = result.scalar_one_or_none()
    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune saison courante définie",
        )
    return season


@router.get("/{season_id}", response_model=SeasonRead)
async def get_season(
    season_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """Retrieve a season by ID."""
    result = await db.execute(select(Season).where(Season.id == season_id))
    season = result.scalar_one_or_none()
    if season is None:
        raise HTTPException(status_code=404, detail="Saison introuvable")
    return season


@router.post("", response_model=SeasonRead, status_code=status.HTTP_201_CREATED)
async def create_season(
    data: SeasonCreate,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """
    Create a new season (admin only).

    If is_current=True, all other seasons are set to is_current=False.
    """
    if data.is_current:
        await db.execute(update(Season).values(is_current=False))

    season = Season(
        name=data.name,
        start_date=data.start_date,
        end_date=data.end_date,
        is_current=data.is_current,
    )
    db.add(season)
    await db.flush()
    return season


@router.put("/{season_id}", response_model=SeasonRead)
async def update_season(
    season_id: UUID,
    data: SeasonUpdate,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Update a season (admin only)."""
    result = await db.execute(select(Season).where(Season.id == season_id))
    season = result.scalar_one_or_none()
    if season is None:
        raise HTTPException(status_code=404, detail="Saison introuvable")

    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("is_current"):
        await db.execute(
            update(Season).where(Season.id != season_id).values(is_current=False)
        )

    for field, value in update_data.items():
        setattr(season, field, value)
    await db.flush()
    return season
