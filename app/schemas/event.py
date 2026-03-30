"""Event Pydantic schemas."""

import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

EventType = Literal[
    "match", "cabaret", "training_show", "training_leisure",
    "welsh", "formation", "ag", "other"
]
EventVisibility = Literal["all", "match", "cabaret", "loisir", "admin"]


class EventBase(BaseModel):
    season_id: uuid.UUID
    venue_id: Optional[uuid.UUID] = None
    title: str
    event_type: EventType
    start_at: datetime
    end_at: Optional[datetime] = None
    is_away: bool = False
    away_city: Optional[str] = None
    away_opponent: Optional[str] = None
    notes: Optional[str] = None
    visibility: EventVisibility = "all"


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    venue_id: Optional[uuid.UUID] = None
    title: Optional[str] = None
    event_type: Optional[EventType] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    is_away: Optional[bool] = None
    away_city: Optional[str] = None
    away_opponent: Optional[str] = None
    notes: Optional[str] = None
    visibility: Optional[EventVisibility] = None


class EventRead(EventBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalendarImportReport(BaseModel):
    created: int = 0
    skipped: int = 0
    errors: List[str] = []
