import pytest


@pytest.mark.asyncio
async def test_list_commissions_requires_auth(client, seeded_data):
    response = await client.get("/commissions")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_commissions_success(regular_client, seeded_data):
    response = await regular_client.get("/commissions")
    assert response.status_code == 200
    assert response.json()[0]["code"] == "COM"


@pytest.mark.asyncio
async def test_add_member_to_commission_success(auth_client, seeded_data):
    response = await auth_client.post(
        f"/commissions/{seeded_data['commission'].id}/members",
        json={
            "member_id": str(seeded_data['admin'].id),
            "season_id": str(seeded_data['current_season'].id),
        },
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_add_member_to_commission_duplicate_returns_409(auth_client, seeded_data):
    payload = {
        "member_id": str(seeded_data['admin'].id),
        "season_id": str(seeded_data['current_season'].id),
    }
    first = await auth_client.post(f"/commissions/{seeded_data['commission'].id}/members", json=payload)
    second = await auth_client.post(f"/commissions/{seeded_data['commission'].id}/members", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_remove_member_from_commission_not_found(auth_client, seeded_data):
    response = await auth_client.delete(
        f"/commissions/{seeded_data['commission'].id}/members/{seeded_data['admin'].id}",
        params={"season_id": str(seeded_data['current_season'].id)},
    )

    assert response.status_code == 404
