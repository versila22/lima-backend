"""Alignment Pydantic schemas."""

import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

from app.schemas.event import EventRead


AlignmentStatus = Literal["draft", "published"]
AssignmentRole = Literal["JR", "DJ", "MJ_MC", "AR", "COACH"]


class AlignmentBase(BaseModel):
    season_id: uuid.UUID
    name: str
    start_date: date
    end_date: date


class AlignmentCreate(AlignmentBase):
    pass


class AlignmentUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[AlignmentStatus] = None


class AssignmentRead(BaseModel):
    id: uuid.UUID
    alignment_id: uuid.UUID
    event_id: uuid.UUID
    member_id: uuid.UUID
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AlignmentEventRead(BaseModel):
    alignment_id: uuid.UUID
    event_id: uuid.UUID
    sort_order: int
    event: Optional[EventRead] = None

    model_config = {"from_attributes": True}


class AlignmentRead(AlignmentBase):
    id: uuid.UUID
    status: str
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlignmentDetail(AlignmentRead):
    """Full alignment with events and assignments."""
    alignment_events: List[AlignmentEventRead] = []
    assignments: List[AssignmentRead] = []


class AddEventsRequest(BaseModel):
    event_ids: List[uuid.UUID]


class AssignRequest(BaseModel):
    member_id: uuid.UUID
    event_id: uuid.UUID
    role: AssignmentRole
