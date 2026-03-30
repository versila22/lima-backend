"""ShowPlan Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel


ShowType = Literal["match", "cabaret", "catch", "other"]


class ShowPlanBase(BaseModel):
    event_id: Optional[uuid.UUID] = None
    title: str
    show_type: ShowType
    theme: Optional[str] = None
    duration: Optional[str] = None
    venue_name: Optional[str] = None
    venue_contact: Optional[str] = None
    config: Dict[str, Any] = {}


class ShowPlanCreate(ShowPlanBase):
    pass


class ShowPlanUpdate(BaseModel):
    event_id: Optional[uuid.UUID] = None
    title: Optional[str] = None
    show_type: Optional[ShowType] = None
    theme: Optional[str] = None
    duration: Optional[str] = None
    venue_name: Optional[str] = None
    venue_contact: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    generated_plan: Optional[str] = None


class ShowPlanRead(ShowPlanBase):
    id: uuid.UUID
    created_by: uuid.UUID
    generated_plan: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
