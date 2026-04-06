from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.member import Member
from app.utils.security import verify_password
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_login_success(client, seeded_data):
    response = await client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "Admin1234!"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_401(client, seeded_data):
    response = await client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_member_returns_403(client, seeded_data):
    response = await client.post(
        "/auth/login",
        json={"email": "inactive@example.com", "password": "Inactive1234!"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_activate_account_success(client, seeded_data):
    response = await client.post(
        "/auth/activate",
        json={"token": "activate-token", "password": "NewPassword123!"},
    )

    assert response.status_code == 200

    async with TestingSessionLocal() as session:
        member = (
            await session.execute(
                select(Member).where(Member.email == "pending@example.com")
            )
        ).scalar_one()
        assert member.is_active is True
        assert member.activation_token is None
        assert verify_password("NewPassword123!", member.password_hash)


@pytest.mark.asyncio
async def test_activate_account_invalid_token_returns_400(client, seeded_data):
    response = await client.post(
        "/auth/activate",
        json={"token": "missing", "password": "NewPassword123!"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_activate_account_expired_token_returns_400(client, seeded_data):
    response = await client.post(
        "/auth/activate",
        json={"token": "expired-activate-token", "password": "NewPassword123!"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_activate_account_validation_returns_422(client, seeded_data):
    response = await client.post(
        "/auth/activate",
        json={"token": "activate-token", "password": "short"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_forgot_password_is_idempotent(client, seeded_data):
    known = await client.post("/auth/forgot-password", json={"email": "reset@example.com"})
    unknown = await client.post("/auth/forgot-password", json={"email": "nobody@example.com"})

    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json()["detail"] == unknown.json()["detail"]

    async with TestingSessionLocal() as session:
        member = (
            await session.execute(select(Member).where(Member.email == "reset@example.com"))
        ).scalar_one()
        assert member.reset_token is not None
        assert member.reset_expires_at > datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)


@pytest.mark.asyncio
async def test_reset_password_success(client, seeded_data):
    await client.post("/auth/forgot-password", json={"email": "reset@example.com"})

    async with TestingSessionLocal() as session:
        member = (
            await session.execute(select(Member).where(Member.email == "reset@example.com"))
        ).scalar_one()
        token = member.reset_token

    response = await client.post(
        "/auth/reset-password",
        json={"token": token, "password": "BrandNew123!"},
    )

    assert response.status_code == 200

    async with TestingSessionLocal() as session:
        member = (
            await session.execute(select(Member).where(Member.email == "reset@example.com"))
        ).scalar_one()
        assert member.reset_token is None
        assert verify_password("BrandNew123!", member.password_hash)


@pytest.mark.asyncio
async def test_reset_password_invalid_token_returns_400(client, seeded_data):
    response = await client.post(
        "/auth/reset-password",
        json={"token": "bad-token", "password": "BrandNew123!"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_me_requires_auth(client, seeded_data):
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_returns_profile(regular_client, seeded_data):
    response = await regular_client.get("/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "member@example.com"
    assert body["player_status"] == "M"
    assert body["asso_role"] == "trésorier"
    assert body["commissions"] == ["Communication"]
    assert body["season_history"][0]["season_name"] == "2025-2026"


@pytest.mark.asyncio
async def test_update_me_updates_profile(regular_client, seeded_data):
    response = await regular_client.put(
        "/auth/me",
        json={"city": "Angers", "phone": "0601020304"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["city"] == "Angers"
    assert body["phone"] == "0601020304"


@pytest.mark.asyncio
async def test_change_password_success(regular_client, seeded_data):
    response = await regular_client.put(
        "/auth/me/password",
        json={
            "current_password": "Member1234!",
            "new_password": "Changed1234!",
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current_password_returns_400(regular_client, seeded_data):
    response = await regular_client.put(
        "/auth/me/password",
        json={
            "current_password": "wrong",
            "new_password": "Changed1234!",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_change_password_validation_returns_422(regular_client, seeded_data):
    response = await regular_client.put(
        "/auth/me/password",
        json={
            "current_password": "Member1234!",
            "new_password": "short",
        },
    )

    assert response.status_code == 422
