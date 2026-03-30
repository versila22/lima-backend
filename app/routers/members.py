"""Members router — admin management + CSV import."""

import uuid
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.member import Member
from app.models.member_season import MemberSeason
from app.schemas.member import (
    ImportMemberReport,
    MemberCreate,
    MemberRead,
    MemberRoleUpdate,
    MemberSummary,
    MemberUpdate,
)
from app.services import auth_service, import_service
from app.utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=List[MemberSummary])
async def list_members(
    season_id: Optional[UUID] = Query(None, description="Filtrer par saison"),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """
    List members, optionally filtered by season or active status.

    Any authenticated user can access this endpoint.
    """
    query = select(Member)
    if is_active is not None:
        query = query.where(Member.is_active == is_active)
    if season_id is not None:
        query = query.join(MemberSeason).where(MemberSeason.season_id == season_id)
    result = await db.execute(query.order_by(Member.last_name, Member.first_name))
    return result.scalars().all()


@router.get("/{member_id}", response_model=MemberRead)
async def get_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """Retrieve full details of a member by ID."""
    result = await db.execute(
        select(Member)
        .options(selectinload(Member.member_seasons))
        .where(Member.id == member_id)
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    return member


@router.post("", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
async def create_member(
    data: MemberCreate,
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(require_admin),
):
    """
    Create a new member manually (admin only).

    Generates an activation token that should be sent by email.
    """
    # Check unique email
    existing = await db.execute(
        select(Member).where(Member.email == data.email.lower())
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un membre avec cet email existe déjà",
        )

    member = Member(
        email=data.email.lower(),
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        date_of_birth=data.date_of_birth,
        address=data.address,
        postal_code=data.postal_code,
        city=data.city,
        app_role=data.app_role,
    )
    db.add(member)
    await db.flush()

    # Generate activation token
    await auth_service.generate_activation_token(db, member)
    # TODO: Send activation email

    return member


@router.put("/{member_id}", response_model=MemberRead)
async def update_member(
    member_id: UUID,
    data: MemberUpdate,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Update a member's information (admin only)."""
    result = await db.execute(select(Member).where(Member.id == member_id))
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Membre introuvable")

    update_data = data.model_dump(exclude_unset=True)
    if "email" in update_data:
        update_data["email"] = update_data["email"].lower()
        # Check for duplicate email
        dup = await db.execute(
            select(Member).where(
                Member.email == update_data["email"],
                Member.id != member_id,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet email est déjà utilisé par un autre membre",
            )

    for field, value in update_data.items():
        setattr(member, field, value)
    await db.flush()
    return member


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Deactivate a member (soft-delete). Admin only."""
    result = await db.execute(select(Member).where(Member.id == member_id))
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    member.is_active = False
    await db.flush()


@router.post("/{member_id}/resend-activation", status_code=status.HTTP_200_OK)
async def resend_activation(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Regenerate and (optionally) resend the activation email. Admin only."""
    result = await db.execute(select(Member).where(Member.id == member_id))
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    if member.password_hash is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce membre a déjà activé son compte",
        )

    token = await auth_service.generate_activation_token(db, member)
    # TODO: Send email with token
    return {"detail": "Email d'activation envoyé", "token": token}


@router.put("/{member_id}/role", response_model=MemberRead)
async def update_member_role(
    member_id: UUID,
    data: MemberRoleUpdate,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Change a member's application role (admin only)."""
    result = await db.execute(select(Member).where(Member.id == member_id))
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    member.app_role = data.app_role
    await db.flush()
    return member


@router.post("/import", response_model=ImportMemberReport)
async def import_members(
    season_id: UUID = Query(..., description="Saison cible"),
    adherents: UploadFile = File(..., description="CSV adhérents HelloAsso"),
    joueurs: UploadFile = File(..., description="CSV joueurs HelloAsso"),
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """
    Import members from two HelloAsso CSV exports (admin only).

    - **adherents**: CSV export des adhérents (cotisation de base)
    - **joueurs**: CSV export des joueurs (cotisation joueur)

    Members are matched by email. Creates or updates records and member_seasons.
    """
    adherents_bytes = await adherents.read()
    joueurs_bytes = await joueurs.read()

    report = await import_service.import_csv_helloasso(
        db, adherents_bytes, joueurs_bytes, season_id
    )
    return report
