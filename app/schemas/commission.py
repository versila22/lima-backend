"""Commission Pydantic schemas."""

import uuid
from typing import Optional

from pydantic import BaseModel


class CommissionRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class AddCommissionMemberRequest(BaseModel):
    member_id: uuid.UUID
    season_id: uuid.UUID
