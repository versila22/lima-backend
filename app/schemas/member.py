"""Member-related Pydantic schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr


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
    season_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------- Member ----------

class MemberBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    photo_url: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    photo_url: Optional[str] = None


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
    photo_url: Optional[str] = None


class MemberProfileUpdate(BaseModel):
    """Self-update by authenticated member (no role change)."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    photo_url: Optional[str] = None


class MemberRoleUpdate(BaseModel):
    app_role: Literal["admin", "member"]


class MemberRead(MemberBase):
    id: uuid.UUID
    app_role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    member_seasons: List[MemberSeasonRead] = []
    player_status: Optional[Literal["M", "C", "L", "A"]] = None
    asso_role: Optional[str] = None
    commissions: List[str] = []

    model_config = {"from_attributes": True}


class MemberSummary(BaseModel):
    """Lightweight member for lists."""
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    photo_url: Optional[str] = None
    app_role: str
    is_active: bool
    player_status: Optional[Literal["M", "C", "L", "A"]] = None

    model_config = {"from_attributes": True}


class SeasonHistoryEntry(BaseModel):
    season_id: uuid.UUID
    season_name: str
    player_status: Literal["M", "C", "L", "A"]
    asso_role: Optional[str] = None


class MemberProfileRead(MemberRead):
    season_history: List[SeasonHistoryEntry] = []


# ---------- Planning ----------

class PlanningEvent(BaseModel):
    event_id: uuid.UUID
    title: str
    event_type: str
    start_at: datetime
    end_at: Optional[datetime] = None
    venue_name: Optional[str] = None
    role: str
    alignment_name: str
    alignment_status: Literal["draft", "published"]


class MemberPlanning(BaseModel):
    upcoming: List[PlanningEvent] = []
    past: List[PlanningEvent] = []
    total_shows: int = 0


# ---------- Import report ----------

class ImportMemberReport(BaseModel):
    created: int = 0
    updated: int = 0
    errors: List[str] = []
    members: List[MemberSummary] = []
