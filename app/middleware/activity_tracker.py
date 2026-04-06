"""Middleware to persist API activity logs."""

import asyncio
import logging
import time
from typing import Optional
from uuid import UUID

from fastapi import Request
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import AsyncSessionLocal
from app.models.activity_log import ActivityLog
from app.utils.security import decode_access_token

logger = logging.getLogger(__name__)

SKIPPED_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class ActivityTrackerMiddleware(BaseHTTPMiddleware):
    enabled: bool = True

    async def dispatch(self, request: Request, call_next):
        if not self.enabled or request.url.path in SKIPPED_PATHS:
            return await call_next(request)

        started_at = time.perf_counter()
        response = None

        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            status_code = response.status_code if response is not None else 500
            activity_data = {
                "user_id": self._extract_user_id(request),
                "method": request.method,
                "path": request.url.path,
                "query_params": request.url.query[:1000] or None,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "user_agent": (request.headers.get("user-agent") or None),
                "ip": self._extract_ip(request),
            }
            asyncio.create_task(self._write_activity_log(activity_data))

    def _extract_user_id(self, request: Request) -> Optional[UUID]:
        authorization = request.headers.get("authorization")
        if not authorization:
            return None

        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None

        try:
            payload = decode_access_token(token)
        except JWTError:
            return None

        subject = payload.get("sub")
        if not subject:
            return None

        try:
            return UUID(str(subject))
        except (TypeError, ValueError):
            return None

    def _extract_ip(self, request: Request) -> Optional[str]:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()[:45] or None

        if request.client and request.client.host:
            return request.client.host[:45]
        return None

    async def _write_activity_log(self, activity_data: dict) -> None:
        async with AsyncSessionLocal() as session:
            try:
                session.add(ActivityLog(**activity_data))
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("Failed to write activity log")
