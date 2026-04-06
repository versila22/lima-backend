"""Members router — admin management + CSV import."""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.alignment import Alignment, AlignmentAssignment, AlignmentEvent
from app.models.commission import Commission, MemberCommission
from app.models.event import Event
from app.models.member import Member
from app.models.member_season import MemberSeason
from app.models.season import Season
from app.models.venue import Venue
from app.schemas.member import (
    MemberPlanning,
    PlanningEvent,
    ImportMemberReport,
    MemberCreate,
    MemberProfileRead,
    MemberRead,
    MemberRoleUpdate,
    MemberSummary,
    MemberUpdate,
    SeasonHistoryEntry,
)
from app.services import auth_service, import_service
from app.services.email_service import send_activation_email
from app.utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/members", tags=["members"])


async def _get_member_for_response(db: AsyncSession, member_id: UUID) -> Member:
    result = await db.execute(
        select(Member)
        .options(selectinload(Member.member_seasons).selectinload(MemberSeason.season))
        .where(Member.id == member_id)
    )
    return result.scalar_one()


async def _build_member_profile(db: AsyncSession, member_id: UUID) -> MemberProfileRead:
    member = await _get_member_for_response(db, member_id)

    current_season_result = await db.execute(
        select(Season).where(Season.is_current.is_(True)).limit(1)
    )
    current_season = current_season_result.scalar_one_or_none()

    current_membership = None
    if current_season is not None:
        current_membership = next(
            (ms for ms in member.member_seasons if ms.season_id == current_season.id),
            None,
        )

    commission_names: list[str] = []
    if current_season is not None:
        commissions_result = await db.execute(
            select(Commission.name)
            .join(MemberCommission, MemberCommission.commission_id == Commission.id)
            .where(
                MemberCommission.member_id == member_id,
                MemberCommission.season_id == current_season.id,
            )
            .order_by(Commission.name)
        )
        commission_names = list(commissions_result.scalars().all())

    base_payload = MemberRead.model_validate(member).model_dump()
    base_payload["member_seasons"] = [
        {
            **season_payload,
            "season_name": member_season.season.name if member_season.season else None,
        }
        for season_payload, member_season in zip(
            base_payload["member_seasons"], member.member_seasons
        )
    ]
    base_payload["player_status"] = (
        current_membership.player_status if current_membership else None
    )
    base_payload["asso_role"] = current_membership.asso_role if current_membership else None
    base_payload["commissions"] = commission_names
    base_payload["season_history"] = [
        SeasonHistoryEntry(
            season_id=member_season.season_id,
            season_name=(
                member_season.season.name if member_season.season else "Saison inconnue"
            ),
            player_status=member_season.player_status,
            asso_role=member_season.asso_role,
        ).model_dump()
        for member_season in sorted(
            member.member_seasons,
            key=lambda ms: (
                ms.season.start_date if ms.season else datetime.min.date(),
                ms.created_at,
            ),
            reverse=True,
        )
    ]

    return MemberProfileRead(**base_payload)


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
    effective_season_id = season_id
    if effective_season_id is None:
        current_season_result = await db.execute(
            select(Season).where(Season.is_current.is_(True)).limit(1)
        )
        current_season = current_season_result.scalar_one_or_none()
        effective_season_id = current_season.id if current_season else None

    query = select(Member).options(selectinload(Member.member_seasons))
    if is_active is not None:
        query = query.where(Member.is_active == is_active)
    if season_id is not None:
        query = query.join(MemberSeason).where(MemberSeason.season_id == season_id)
    result = await db.execute(query.order_by(Member.last_name, Member.first_name))
    members = result.scalars().unique().all()

    summaries = []
    for member in members:
        player_status = None
        if effective_season_id is not None:
            season_entry = next(
                (
                    ms
                    for ms in member.member_seasons
                    if ms.season_id == effective_season_id
                ),
                None,
            )
            if season_entry is not None:
                player_status = season_entry.player_status

        summaries.append(
            MemberSummary(
                id=member.id,
                email=member.email,
                first_name=member.first_name,
                last_name=member.last_name,
                app_role=member.app_role,
                is_active=member.is_active,
                player_status=player_status,
            )
        )
    return summaries


@router.get("/{member_id}/profile", response_model=MemberProfileRead)
async def get_member_profile(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """Retrieve the enriched profile of a member.

    A member can view their own profile; admins can view any member.
    """
    if not current_user.is_admin and current_user.id != member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé à votre profil",
        )

    result = await db.execute(select(Member.id).where(Member.id == member_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Membre introuvable")

    return await _build_member_profile(db, member_id)


@router.get("/{member_id}", response_model=MemberRead)
async def get_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(get_current_user),
):
    """Retrieve full details of a member by ID."""
    result = await db.execute(
        select(Member)
        .options(selectinload(Member.member_seasons).selectinload(MemberSeason.season))
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
    token = await auth_service.generate_activation_token(db, member)
    await send_activation_email(
        to=member.email,
        first_name=member.first_name,
        token=token,
        base_url=settings.FRONTEND_URL,
    )

    return await _get_member_for_response(db, member.id)


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
    return await _get_member_for_response(db, member.id)


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
    await send_activation_email(
        to=member.email,
        first_name=member.first_name,
        token=token,
        base_url=settings.FRONTEND_URL,
    )
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
    return await _get_member_for_response(db, member.id)


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


@router.get("/me/planning", response_model=MemberPlanning)
async def get_my_planning(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current member's planning: upcoming and past show assignments."""
    from datetime import timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    three_months_ago = now - timedelta(days=90)

    # Query all assignments for this member with event + alignment data
    stmt = (
        select(AlignmentAssignment, AlignmentEvent, Event, Alignment)
        .join(AlignmentEvent, AlignmentAssignment.alignment_event_id == AlignmentEvent.id)
        .join(Event, AlignmentEvent.event_id == Event.id)
        .join(Alignment, AlignmentAssignment.alignment_id == Alignment.id)
        .where(AlignmentAssignment.member_id == current_user.id)
        .where(Event.start_at >= three_months_ago)
        .order_by(Event.start_at.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    upcoming: list[PlanningEvent] = []
    past: list[PlanningEvent] = []

    for assignment, alignment_event, event, alignment in rows:
        # Get venue name
        venue_name = None
        if event.venue_id:
            venue = await db.get(Venue, event.venue_id)
            venue_name = venue.name if venue else None

        pe = PlanningEvent(
            event_id=event.id,
            title=event.title,
            event_type=event.event_type,
            start_at=event.start_at,
            end_at=event.end_at,
            venue_name=venue_name,
            role=assignment.role,
            alignment_name=alignment.name,
            alignment_status=alignment.status,
        )
        if event.start_at >= now:
            upcoming.append(pe)
        else:
            past.append(pe)

    past.sort(key=lambda e: e.start_at, reverse=True)

    return MemberPlanning(
        upcoming=upcoming,
        past=past,
        total_shows=len(rows),
    )
