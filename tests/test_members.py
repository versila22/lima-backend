import pytest


@pytest.mark.asyncio
async def test_list_members_requires_auth(client, seeded_data):
    response = await client.get("/members")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_members_filters_by_season(regular_client, seeded_data):
    response = await regular_client.get(
        "/members",
        params={"season_id": str(seeded_data["current_season"].id)},
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_member_returns_404_for_unknown_id(regular_client, seeded_data):
    response = await regular_client.get("/members/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_member_profile_returns_enriched_context(regular_client, seeded_data):
    response = await regular_client.get(f"/members/{seeded_data['regular'].id}/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["player_status"] == "M"
    assert body["asso_role"] == "trésorier"
    assert body["commissions"] == ["Communication"]
    assert len(body["season_history"]) == 2
    assert body["season_history"][0]["season_name"] == "2025-2026"


@pytest.mark.asyncio
async def test_get_member_profile_forbidden_for_other_member(regular_client, seeded_data):
    response = await regular_client.get(f"/members/{seeded_data['admin'].id}/profile")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_member_requires_admin(regular_client, seeded_data):
    response = await regular_client.post(
        "/members",
        json={
            "email": "new@example.com",
            "first_name": "New",
            "last_name": "Member",
            "app_role": "member",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_member_success(auth_client, seeded_data):
    response = await auth_client.post(
        "/members",
        json={
            "email": "new@example.com",
            "first_name": "New",
            "last_name": "Member",
            "app_role": "member",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert body["app_role"] == "member"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_create_member_duplicate_email_returns_409(auth_client, seeded_data):
    response = await auth_client.post(
        "/members",
        json={
            "email": "member@example.com",
            "first_name": "Dup",
            "last_name": "Member",
            "app_role": "member",
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_member_validation_returns_422(auth_client, seeded_data):
    response = await auth_client.post(
        "/members",
        json={"email": "bad-email", "first_name": "A"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_member_success(auth_client, seeded_data):
    response = await auth_client.put(
        f"/members/{seeded_data['regular'].id}",
        json={"email": "updated@example.com", "city": "Angers"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "updated@example.com"
    assert body["city"] == "Angers"


@pytest.mark.asyncio
async def test_update_member_duplicate_email_returns_409(auth_client, seeded_data):
    response = await auth_client.put(
        f"/members/{seeded_data['regular'].id}",
        json={"email": "admin@example.com"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_member_unknown_returns_404(auth_client, seeded_data):
    response = await auth_client.put(
        "/members/00000000-0000-0000-0000-000000000001",
        json={"city": "Nantes"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_deactivate_member_success(auth_client, seeded_data):
    response = await auth_client.delete(f"/members/{seeded_data['regular'].id}")
    assert response.status_code == 204

    get_response = await auth_client.get(f"/members/{seeded_data['regular'].id}")
    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_deactivate_member_not_found(auth_client, seeded_data):
    response = await auth_client.delete("/members/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_resend_activation_returns_token(auth_client, seeded_data):
    response = await auth_client.post(f"/members/{seeded_data['pending'].id}/resend-activation")

    assert response.status_code == 200
    assert response.json()["token"]


@pytest.mark.asyncio
async def test_resend_activation_rejects_already_activated_member(auth_client, seeded_data):
    response = await auth_client.post(f"/members/{seeded_data['regular'].id}/resend-activation")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_member_role_success(auth_client, seeded_data):
    response = await auth_client.put(
        f"/members/{seeded_data['regular'].id}/role",
        json={"app_role": "admin"},
    )

    assert response.status_code == 200
    assert response.json()["app_role"] == "admin"
