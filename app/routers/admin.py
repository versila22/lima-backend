"""Admin router for activity monitoring."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, Float, and_, case, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.activity_log import ActivityLog
from app.models.member import Member
from app.schemas.activity import (
    ActivityLogRead,
    ActivityStatsResponse,
    DailyActiveUserStat,
    EndpointStat,
    LoginAttemptGroup,
    LoginAttemptRead,
    LoginAttemptsResponse,
)
from app.utils.deps import require_admin

router = APIRouter(tags=["admin"])


@router.get("/activity/recent", response_model=List[ActivityLogRead])
async def get_recent_activity(
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[UUID] = Query(None),
    path_prefix: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Return recent activity logs with optional filters."""
    query = select(ActivityLog).options(selectinload(ActivityLog.user))

    if user_id is not None:
        query = query.where(ActivityLog.user_id == user_id)
    if path_prefix:
        query = query.where(ActivityLog.path.like(f"{path_prefix}%"))

    result = await db.execute(
        query.order_by(ActivityLog.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.get("/activity/stats", response_model=ActivityStatsResponse)
async def get_activity_stats(
    days: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Return aggregate activity statistics for the given period."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    base_filter = ActivityLog.created_at >= since

    total_requests = await db.scalar(
        select(func.count(ActivityLog.id)).where(base_filter)
    )
    unique_users = await db.scalar(
        select(func.count(distinct(ActivityLog.user_id))).where(
            base_filter,
            ActivityLog.user_id.is_not(None),
        )
    )
    avg_response_time_ms = await db.scalar(
        select(func.avg(cast(ActivityLog.duration_ms, Float))).where(base_filter)
    )

    top_endpoints_result = await db.execute(
        select(ActivityLog.path, func.count(ActivityLog.id).label("count"))
        .where(base_filter)
        .group_by(ActivityLog.path)
        .order_by(func.count(ActivityLog.id).desc(), ActivityLog.path)
        .limit(10)
    )

    error_endpoints_result = await db.execute(
        select(ActivityLog.path, func.count(ActivityLog.id).label("count"))
        .where(base_filter, ActivityLog.status_code >= 400)
        .group_by(ActivityLog.path)
        .order_by(func.count(ActivityLog.id).desc(), ActivityLog.path)
        .limit(10)
    )

    daily_active_users_result = await db.execute(
        select(
            cast(func.date_trunc("day", ActivityLog.created_at), Date).label("day"),
            func.count(distinct(ActivityLog.user_id)).label("unique_users"),
        )
        .where(base_filter, ActivityLog.user_id.is_not(None))
        .group_by(func.date_trunc("day", ActivityLog.created_at))
        .order_by(func.date_trunc("day", ActivityLog.created_at))
    )

    return ActivityStatsResponse(
        total_requests=total_requests or 0,
        unique_users=unique_users or 0,
        top_endpoints=[EndpointStat(path=path, count=count) for path, count in top_endpoints_result.all()],
        error_endpoints=[EndpointStat(path=path, count=count) for path, count in error_endpoints_result.all()],
        daily_active_users=[
            DailyActiveUserStat(day=day, unique_users=unique_users)
            for day, unique_users in daily_active_users_result.all()
        ],
        avg_response_time_ms=round(float(avg_response_time_ms or 0), 2),
    )


@router.get("/activity/logins", response_model=LoginAttemptsResponse)
async def get_login_attempts(
    days: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Return login attempts and success/failure summary for the given period."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    login_filter = and_(
        ActivityLog.created_at >= since,
        ActivityLog.method == "POST",
        ActivityLog.path.in_(["/auth/login", "/api/auth/login"]),
    )

    summary_result = await db.execute(
        select(
            case(
                (ActivityLog.status_code < 400, "success"),
                else_="failure",
            ).label("outcome"),
            func.count(ActivityLog.id).label("count"),
        )
        .where(login_filter)
        .group_by(
            case(
                (ActivityLog.status_code < 400, "success"),
                else_="failure",
            )
        )
        .order_by("outcome")
    )

    attempts_result = await db.execute(
        select(ActivityLog)
        .options(selectinload(ActivityLog.user))
        .where(login_filter)
        .order_by(ActivityLog.created_at.desc())
        .limit(200)
    )

    return LoginAttemptsResponse(
        days=days,
        summary=[
            LoginAttemptGroup(outcome=outcome, count=count)
            for outcome, count in summary_result.all()
        ],
        attempts=[LoginAttemptRead.model_validate(item) for item in attempts_result.scalars().all()],
    )
