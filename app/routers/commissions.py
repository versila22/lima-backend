"""Commissions router."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.commission import Commission, MemberCommission
from app.models.member import Member
from app.schemas.commission import AddCommissionMemberRequest, CommissionRead
from app.utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/commissions", tags=["commissions"])


@router.get("", response_model=List[CommissionRead])
async def list_commissions(
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """List all commissions."""
    result = await db.execute(select(Commission).order_by(Commission.name))
    return result.scalars().all()


@router.post("/{commission_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member_to_commission(
    commission_id: UUID,
    data: AddCommissionMemberRequest,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Assign a member to a commission for a given season (admin only)."""
    # Verify commission
    comm_result = await db.execute(
        select(Commission).where(Commission.id == commission_id)
    )
    if comm_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Commission introuvable")

    # Check not already assigned
    existing = await db.execute(
        select(MemberCommission).where(
            MemberCommission.commission_id == commission_id,
            MemberCommission.member_id == data.member_id,
            MemberCommission.season_id == data.season_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce membre est déjà dans cette commission pour cette saison",
        )

    mc = MemberCommission(
        commission_id=commission_id,
        member_id=data.member_id,
        season_id=data.season_id,
    )
    db.add(mc)
    await db.flush()
    return {"detail": "Membre ajouté à la commission"}


@router.delete(
    "/{commission_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member_from_commission(
    commission_id: UUID,
    member_id: UUID,
    season_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Remove a member from a commission (admin only)."""
    result = await db.execute(
        select(MemberCommission).where(
            MemberCommission.commission_id == commission_id,
            MemberCommission.member_id == member_id,
            MemberCommission.season_id == season_id,
        )
    )
    mc = result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(status_code=404, detail="Affectation introuvable")
    await db.delete(mc)
    await db.flush()
