"""Show plans router."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.member import Member
from app.models.season import Season
from app.models.show_plan import ShowPlan
from app.schemas.show_plan import ShowPlanCreate, ShowPlanRead, ShowPlanUpdate
from app.utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/show-plans", tags=["show-plans"])


@router.get("", response_model=List[ShowPlanRead])
async def list_show_plans(
    season_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """
    List show plans.

    If season_id is provided, filters by events in that season.
    Otherwise returns plans for the current season.
    """
    query = select(ShowPlan).order_by(ShowPlan.created_at.desc())

    if season_id:
        from app.models.event import Event
        query = query.join(Event, ShowPlan.event_id == Event.id, isouter=True).where(
            Event.season_id == season_id
        )
    else:
        # Default to current season
        season_result = await db.execute(
            select(Season).where(Season.is_current)
        )
        current_season = season_result.scalar_one_or_none()
        if current_season:
            from app.models.event import Event
            query = query.join(
                Event, ShowPlan.event_id == Event.id, isouter=True
            ).where(Event.season_id == current_season.id)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{plan_id}", response_model=ShowPlanRead)
async def get_show_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """Retrieve a show plan by ID."""
    result = await db.execute(select(ShowPlan).where(ShowPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan introuvable")
    return plan


@router.post("", response_model=ShowPlanRead, status_code=status.HTTP_201_CREATED)
async def create_show_plan(
    data: ShowPlanCreate,
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(require_admin),
):
    """Create a new show plan (admin only)."""
    plan = ShowPlan(**data.model_dump(), created_by=admin.id)
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return plan


@router.put("/{plan_id}", response_model=ShowPlanRead)
async def update_show_plan(
    plan_id: UUID,
    data: ShowPlanUpdate,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Update a show plan (admin only)."""
    result = await db.execute(select(ShowPlan).where(ShowPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.flush()
    await db.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_show_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Delete a show plan (admin only)."""
    result = await db.execute(select(ShowPlan).where(ShowPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan introuvable")
    await db.delete(plan)
    await db.flush()
