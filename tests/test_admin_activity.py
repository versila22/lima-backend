from datetime import UTC, datetime, timedelta

import pytest

from app.models.activity_log import ActivityLog
from tests.conftest import TestingSessionLocal


async def _seed_activity_logs(seeded_data):
    async with TestingSessionLocal() as session:
        now = datetime.now(UTC).replace(tzinfo=None)
        session.add_all(
            [
                ActivityLog(
                    user_id=seeded_data["admin"].id,
                    method="GET",
                    path="/members",
                    query_params=None,
                    status_code=200,
                    duration_ms=20,
                    user_agent="pytest",
                    ip="127.0.0.1",
                    created_at=now - timedelta(hours=2),
                ),
                ActivityLog(
                    user_id=seeded_data["regular"].id,
                    method="POST",
                    path="/auth/login",
                    query_params=None,
                    status_code=200,
                    duration_ms=30,
                    user_agent="pytest",
                    ip="127.0.0.1",
                    created_at=now - timedelta(hours=1),
                ),
                ActivityLog(
                    user_id=None,
                    method="POST",
                    path="/auth/login",
                    query_params=None,
                    status_code=401,
                    duration_ms=25,
                    user_agent="pytest",
                    ip="127.0.0.2",
                    created_at=now - timedelta(minutes=30),
                ),
                ActivityLog(
                    user_id=seeded_data["regular"].id,
                    method="GET",
                    path="/events",
                    query_params="season_id=test",
                    status_code=500,
                    duration_ms=80,
                    user_agent="pytest",
                    ip="127.0.0.1",
                    created_at=now - timedelta(minutes=10),
                ),
            ]
        )
        await session.commit()


@pytest.mark.asyncio
async def test_recent_activity_requires_admin(regular_client, seeded_data):
    response = await regular_client.get("/api/admin/activity/recent")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_recent_activity_returns_filtered_logs(auth_client, seeded_data):
    await _seed_activity_logs(seeded_data)

    response = await auth_client.get(
        "/api/admin/activity/recent",
        params={"path_prefix": "/auth", "limit": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert all(item["path"].startswith("/auth") for item in body)


@pytest.mark.asyncio
async def test_activity_stats_returns_aggregates(auth_client, seeded_data):
    await _seed_activity_logs(seeded_data)

    response = await auth_client.get("/api/admin/activity/stats", params={"days": 7})

    assert response.status_code == 200
    body = response.json()
    assert body["total_requests"] >= 4
    assert body["unique_users"] >= 2
    assert body["avg_response_time_ms"] > 0
    assert any(item["path"] == "/auth/login" for item in body["top_endpoints"])
    assert any(item["path"] == "/events" for item in body["error_endpoints"])


@pytest.mark.asyncio
async def test_login_attempts_groups_success_and_failure(auth_client, seeded_data):
    await _seed_activity_logs(seeded_data)

    response = await auth_client.get("/api/admin/activity/logins", params={"days": 7})

    assert response.status_code == 200
    body = response.json()
    outcomes = {item["outcome"]: item["count"] for item in body["summary"]}
    assert outcomes["success"] == 1
    assert outcomes["failure"] == 1
    assert len(body["attempts"]) == 2
