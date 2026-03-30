"""Authentication service — login, activation, password reset."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.member import Member
from app.utils.security import (
    generate_secure_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)


async def authenticate_member(
    db: AsyncSession, email: str, password: str
) -> Optional[Member]:
    """
    Validate email/password credentials.

    Returns the Member on success, None on failure.
    """
    result = await db.execute(
        select(Member).where(Member.email == email.lower().strip())
    )
    member = result.scalar_one_or_none()
    if member is None:
        return None
    if member.password_hash is None:
        return None
    if not verify_password(password, member.password_hash):
        return None
    return member


async def activate_account(
    db: AsyncSession, token: str, password: str
) -> Member:
    """
    Activate a member account using the one-time activation token.

    Raises ValueError if the token is invalid or expired.
    """
    result = await db.execute(
        select(Member).where(Member.activation_token == token)
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise ValueError("Token d'activation invalide")
    if member.activation_expires_at and member.activation_expires_at < datetime.now(
        timezone.utc
    ):
        raise ValueError("Token d'activation expiré")

    member.password_hash = hash_password(password)
    member.activation_token = None
    member.activation_expires_at = None
    member.is_active = True
    await db.flush()
    return member


async def generate_activation_token(db: AsyncSession, member: Member) -> str:
    """Create and persist a new activation token (valid 7 days)."""
    token = generate_secure_token()
    member.activation_token = token
    member.activation_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.flush()
    return token


async def request_password_reset(
    db: AsyncSession, email: str
) -> Optional[Member]:
    """
    Generate a password-reset token for the given email.

    Returns the Member (with token set) or None if email not found.
    Does NOT raise if email is missing (prevents enumeration).
    """
    result = await db.execute(
        select(Member).where(Member.email == email.lower().strip())
    )
    member = result.scalar_one_or_none()
    if member is None:
        return None

    token = generate_secure_token()
    member.reset_token = token
    member.reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    await db.flush()
    return member


async def reset_password(db: AsyncSession, token: str, password: str) -> Member:
    """
    Reset password using a valid reset token.

    Raises ValueError if the token is invalid or expired.
    """
    result = await db.execute(
        select(Member).where(Member.reset_token == token)
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise ValueError("Token de réinitialisation invalide")
    if member.reset_expires_at and member.reset_expires_at < datetime.now(
        timezone.utc
    ):
        raise ValueError("Token de réinitialisation expiré")

    member.password_hash = hash_password(password)
    member.reset_token = None
    member.reset_expires_at = None
    await db.flush()
    return member
