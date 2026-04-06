"""Activity tracking schemas."""

import uuid
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ActivityLogUser(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str

    model_config = {"from_attributes": True}


class ActivityLogRead(BaseModel):
    id: int
    user_id: Optional[uuid.UUID] = None
    method: str
    path: str
    query_params: Optional[str] = None
    status_code: int
    duration_ms: int
    user_agent: Optional[str] = None
    ip: Optional[str] = None
    created_at: datetime
    user: Optional[ActivityLogUser] = None

    model_config = {"from_attributes": True}


class EndpointStat(BaseModel):
    path: str
    count: int


class DailyActiveUserStat(BaseModel):
    day: date
    unique_users: int


class ActivityStatsResponse(BaseModel):
    total_requests: int
    unique_users: int
    top_endpoints: List[EndpointStat]
    error_endpoints: List[EndpointStat]
    daily_active_users: List[DailyActiveUserStat]
    avg_response_time_ms: float


class LoginAttemptGroup(BaseModel):
    outcome: str
    count: int


class LoginAttemptRead(BaseModel):
    user_id: Optional[uuid.UUID] = None
    status_code: int
    created_at: datetime
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    user: Optional[ActivityLogUser] = None

    model_config = {"from_attributes": True}


class LoginAttemptsResponse(BaseModel):
    days: int
    summary: List[LoginAttemptGroup] = Field(default_factory=list)
    attempts: List[LoginAttemptRead] = Field(default_factory=list)
