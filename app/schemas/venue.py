"""Venue Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class VenueBase(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    contact_info: Optional[str] = None
    is_home: bool = True


class VenueCreate(VenueBase):
    pass


class VenueUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    contact_info: Optional[str] = None
    is_home: Optional[bool] = None


class VenueRead(VenueBase):
    id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
