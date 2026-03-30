"""Authentication router — login, activation, password management."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.member import Member
from app.schemas.auth import (
    ActivateAccountRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.member import MemberProfileUpdate, MemberRead
from app.services import auth_service
from app.utils.deps import get_current_user
from app.utils.security import create_access_token, verify_password, hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
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
async def activate_account(
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
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset email.

    Always returns 200 (no email enumeration).
    """
    member = await auth_service.request_password_reset(db, data.email)
    # TODO: send email when SMTP is configured
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


@router.get("/me", response_model=MemberRead)
async def get_me(current_user: Member = Depends(get_current_user)):
    """Return the profile of the currently authenticated member."""
    return current_user


@router.put("/me", response_model=MemberRead)
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
    return current_user


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
