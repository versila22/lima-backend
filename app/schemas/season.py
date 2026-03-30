"""Season Pydantic schemas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, model_validator


class SeasonBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    is_current: bool = False

    @model_validator(mode="after")
    def end_after_start(self) -> "SeasonBase":
        if self.end_date <= self.start_date:
            raise ValueError("end_date doit être postérieure à start_date")
        return self


class SeasonCreate(SeasonBase):
    pass


class SeasonUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None


class SeasonRead(SeasonBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
