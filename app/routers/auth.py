"""Authentication router — login, activation, password management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.limiting import limiter
from app.models.commission import Commission, MemberCommission
from app.models.member import Member
from app.models.member_season import MemberSeason
from app.models.season import Season
from app.schemas.auth import (
    ActivateAccountRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.member import MemberProfileRead, MemberProfileUpdate, MemberRead, SeasonHistoryEntry
from app.services import auth_service
from app.services.email_service import send_password_reset_email
from app.utils.deps import get_current_user
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


async def _build_member_profile(db: AsyncSession, member_id: UUID) -> MemberProfileRead:
    member_result = await db.execute(
        select(Member)
        .options(selectinload(Member.member_seasons).selectinload(MemberSeason.season))
        .where(Member.id == member_id)
    )
    member = member_result.scalar_one()

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

    season_history = [
        SeasonHistoryEntry(
            season_id=member_season.season_id,
            season_name=member_season.season.name if member_season.season else "Saison inconnue",
            player_status=member_season.player_status,
            asso_role=member_season.asso_role,
        )
        for member_season in sorted(
            member.member_seasons,
            key=lambda ms: (
                ms.season.start_date if ms.season else getattr(ms, "created_at", None),
                ms.created_at,
            ),
            reverse=True,
        )
    ]

    member_seasons = [
        {
            **MemberRead.model_validate(member).model_dump()["member_seasons"][index],
            "season_name": member_season.season.name if member_season.season else None,
        }
        for index, member_season in enumerate(member.member_seasons)
    ]

    payload = MemberRead.model_validate(member).model_dump()
    payload["member_seasons"] = member_seasons
    payload["player_status"] = current_membership.player_status if current_membership else None
    payload["asso_role"] = current_membership.asso_role if current_membership else None
    payload["commissions"] = commission_names
    payload["season_history"] = [entry.model_dump() for entry in season_history]

    return MemberProfileRead(**payload)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with email and password.

    Returns a JWT access token valid for 30 minutes.
    """
    member = await auth_service.authenticate_member(db, data.email, data.password)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not member.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé",
        )

    token = create_access_token(
        subject=str(member.id),
        extra_claims={"role": member.app_role},
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/activate", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def activate_account(
    request: Request,
    data: ActivateAccountRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Activate a member account using the one-time token sent by email.

    Sets the password and marks the account as active.
    """
    try:
        await auth_service.activate_account(db, data.token, data.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"detail": "Compte activé avec succès"}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset email.

    Always returns 200 (no email enumeration).
    """
    member = await auth_service.request_password_reset(db, data.email)
    if member is not None and member.reset_token is not None:
        await send_password_reset_email(
            to=member.email,
            first_name=member.first_name,
            token=member.reset_token,
            base_url=settings.FRONTEND_URL,
        )
    return {"detail": "Si cet email existe, un lien de réinitialisation a été envoyé"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using the token received by email."""
    try:
        await auth_service.reset_password(db, data.token, data.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"detail": "Mot de passe réinitialisé avec succès"}


@router.get("/me", response_model=MemberProfileRead)
async def get_me(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the enriched profile of the currently authenticated member."""
    return await _build_member_profile(db, current_user.id)


@router.put("/me", response_model=MemberProfileRead)
async def update_me(
    data: MemberProfileUpdate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the profile of the currently authenticated member."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    await db.flush()
    return await _build_member_profile(db, current_user.id)


@router.put("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    data: ChangePasswordRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the password of the currently authenticated member."""
    if current_user.password_hash is None or not verify_password(
        data.current_password, current_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect",
        )
    current_user.password_hash = hash_password(data.new_password)
    await db.flush()
    return {"detail": "Mot de passe modifié avec succès"}
