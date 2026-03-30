"""Member-related Pydantic schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, field_validator


# ---------- MemberSeason ----------

class MemberSeasonBase(BaseModel):
    season_id: uuid.UUID
    player_status: Literal["M", "C", "L", "A"] = "A"
    membership_fee: Optional[Decimal] = None
    player_fee: Optional[Decimal] = None
    helloasso_ref: Optional[str] = None
    asso_role: Optional[str] = None


class MemberSeasonCreate(MemberSeasonBase):
    pass


class MemberSeasonRead(MemberSeasonBase):
    id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Member ----------

class MemberBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None


class MemberCreate(MemberBase):
    app_role: Literal["admin", "member"] = "member"


class MemberUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None


class MemberProfileUpdate(BaseModel):
    """Self-update by authenticated member (no role change)."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None


class MemberRoleUpdate(BaseModel):
    app_role: Literal["admin", "member"]


class MemberRead(MemberBase):
    id: uuid.UUID
    app_role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    member_seasons: List[MemberSeasonRead] = []

    model_config = {"from_attributes": True}


class MemberSummary(BaseModel):
    """Lightweight member for lists."""
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    app_role: str
    is_active: bool

    model_config = {"from_attributes": True}


# ---------- Import report ----------

class ImportMemberReport(BaseModel):
    created: int = 0
    updated: int = 0
    errors: List[str] = []
    members: List[MemberSummary] = []
