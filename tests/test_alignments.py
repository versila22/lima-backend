import pytest

from app.routers import alignments as alignments_router


@pytest.mark.asyncio
async def test_regular_user_only_sees_published_alignments(regular_client, seeded_data):
    response = await regular_client.get("/alignments")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == ["Grille publiée"]


@pytest.mark.asyncio
async def test_get_draft_alignment_forbidden_for_regular_user(regular_client, seeded_data):
    response = await regular_client.get(f"/alignments/{seeded_data['draft_alignment'].id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_alignment_requires_admin(regular_client, seeded_data):
    response = await regular_client.post(
        "/alignments",
        json={
            "season_id": str(seeded_data['current_season'].id),
            "name": "Nouvelle grille",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_alignment_success(auth_client, seeded_data):
    response = await auth_client.post(
        "/alignments",
        json={
            "season_id": str(seeded_data['current_season'].id),
            "name": "Nouvelle grille",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Nouvelle grille"
    assert response.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_update_alignment_success(auth_client, seeded_data):
    response = await auth_client.put(
        f"/alignments/{seeded_data['draft_alignment'].id}",
        json={"name": "Grille modifiée", "status": "published"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Grille modifiée"
    assert response.json()["status"] == "published"


@pytest.mark.asyncio
async def test_update_alignment_not_found(auth_client, seeded_data):
    response = await auth_client.put(
        "/alignments/00000000-0000-0000-0000-000000000001",
        json={"name": "Ghost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_add_events_to_alignment_success(auth_client, seeded_data):
    response = await auth_client.post(
        f"/alignments/{seeded_data['published_alignment'].id}/events",
        json={"event_ids": [str(seeded_data['admin_event'].id)]},
    )

    assert response.status_code == 200
    assert "ajouté" in response.json()["detail"]


@pytest.mark.asyncio
async def test_add_events_to_alignment_returns_400_for_unknown_event(auth_client, seeded_data):
    response = await auth_client.post(
        f"/alignments/{seeded_data['published_alignment'].id}/events",
        json={"event_ids": ["00000000-0000-0000-0000-000000000001"]},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_assign_member_success(auth_client, seeded_data):
    response = await auth_client.post(
        f"/alignments/{seeded_data['published_alignment'].id}/assign",
        json={
            "member_id": str(seeded_data['regular'].id),
            "event_id": str(seeded_data['public_event'].id),
            "role": "JR",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "JR"


@pytest.mark.asyncio
async def test_assign_member_sends_email_notification(auth_client, seeded_data, monkeypatch):
    calls = []

    async def fake_send_cast_assignment_email(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        alignments_router,
        "send_cast_assignment_email",
        fake_send_cast_assignment_email,
    )

    response = await auth_client.post(
        f"/alignments/{seeded_data['published_alignment'].id}/assign",
        json={
            "member_id": str(seeded_data['regular'].id),
            "event_id": str(seeded_data['public_event'].id),
            "role": "JR",
        },
    )

    assert response.status_code == 201
    assert len(calls) == 1
    assert calls[0]["to"] == seeded_data["regular"].email
    assert calls[0]["first_name"] == seeded_data["regular"].first_name
    assert calls[0]["event_title"] == seeded_data["public_event"].title
    assert calls[0]["role"] == "JR"
    assert calls[0]["alignment_name"] == seeded_data["published_alignment"].name
    assert calls[0]["base_url"].endswith("lovable.app")


@pytest.mark.asyncio
async def test_assign_member_duplicate_returns_400(auth_client, seeded_data):
    payload = {
        "member_id": str(seeded_data['regular'].id),
        "event_id": str(seeded_data['public_event'].id),
        "role": "JR",
    }
    first = await auth_client.post(f"/alignments/{seeded_data['published_alignment'].id}/assign", json=payload)
    second = await auth_client.post(f"/alignments/{seeded_data['published_alignment'].id}/assign", json=payload)

    assert first.status_code == 201
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_assign_member_event_not_in_alignment_returns_400(auth_client, seeded_data):
    response = await auth_client.post(
        f"/alignments/{seeded_data['published_alignment'].id}/assign",
        json={
            "member_id": str(seeded_data['regular'].id),
            "event_id": str(seeded_data['admin_event'].id),
            "role": "JR",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_remove_event_from_alignment_cascades_assignments(auth_client, seeded_data):
    await auth_client.post(
        f"/alignments/{seeded_data['published_alignment'].id}/assign",
        json={
            "member_id": str(seeded_data['regular'].id),
            "event_id": str(seeded_data['public_event'].id),
            "role": "DJ",
        },
    )

    response = await auth_client.delete(
        f"/alignments/{seeded_data['published_alignment'].id}/events/{seeded_data['public_event'].id}"
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_remove_assignment_sends_email_notification(auth_client, seeded_data, monkeypatch):
    calls = []

    async def fake_send_cast_unassignment_email(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        alignments_router,
        "send_cast_unassignment_email",
        fake_send_cast_unassignment_email,
    )

    create_response = await auth_client.post(
        f"/alignments/{seeded_data['published_alignment'].id}/assign",
        json={
            "member_id": str(seeded_data['regular'].id),
            "event_id": str(seeded_data['public_event'].id),
            "role": "DJ",
        },
    )
    assignment_id = create_response.json()["id"]

    response = await auth_client.delete(
        f"/alignments/{seeded_data['published_alignment'].id}/assign/{assignment_id}"
    )

    assert response.status_code == 204
    assert len(calls) == 1
    assert calls[0]["to"] == seeded_data["regular"].email
    assert calls[0]["first_name"] == seeded_data["regular"].first_name
    assert calls[0]["event_title"] == seeded_data["public_event"].title
    assert calls[0]["role"] == "DJ"
    assert calls[0]["alignment_name"] == seeded_data["published_alignment"].name


@pytest.mark.asyncio
async def test_remove_event_from_alignment_not_found_returns_400(auth_client, seeded_data):
    response = await auth_client.delete(
        f"/alignments/{seeded_data['published_alignment'].id}/events/{seeded_data['admin_event'].id}"
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_publish_alignment_success(auth_client, seeded_data):
    response = await auth_client.put(f"/alignments/{seeded_data['draft_alignment'].id}/publish")

    assert response.status_code == 200
    assert response.json()["status"] == "published"


@pytest.mark.asyncio
async def test_delete_alignment_not_found(auth_client, seeded_data):
    response = await auth_client.delete("/alignments/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404
