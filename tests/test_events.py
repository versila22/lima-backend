from io import BytesIO

import openpyxl
import pytest

from app.models.alignment import AlignmentAssignment


@pytest.mark.asyncio
async def test_list_events_requires_auth(client, seeded_data):
    response = await client.get("/events")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_regular_user_cannot_see_admin_events(regular_client, seeded_data):
    response = await regular_client.get("/events")

    assert response.status_code == 200
    titles = {event["title"] for event in response.json()}
    assert "Match public" in titles
    assert "Réunion CA" not in titles


@pytest.mark.asyncio
async def test_admin_can_filter_events(auth_client, seeded_data):
    response = await auth_client.get(
        "/events",
        params={
            "season_id": str(seeded_data["current_season"].id),
            "event_type": "match",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Match public"


@pytest.mark.asyncio
async def test_get_admin_event_forbidden_for_regular_user(regular_client, seeded_data):
    response = await regular_client.get(f"/events/{seeded_data['admin_event'].id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_event_not_found(auth_client, seeded_data):
    response = await auth_client.get("/events/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_event_cast_returns_assignments(auth_client, seeded_data, db_session):
    db_session.add_all(
        [
            AlignmentAssignment(
                alignment_id=seeded_data["published_alignment"].id,
                event_id=seeded_data["public_event"].id,
                member_id=seeded_data["admin"].id,
                role="COACH",
            ),
            AlignmentAssignment(
                alignment_id=seeded_data["published_alignment"].id,
                event_id=seeded_data["public_event"].id,
                member_id=seeded_data["regular"].id,
                role="JR",
            ),
        ]
    )
    await db_session.commit()

    response = await auth_client.get(f"/events/{seeded_data['public_event'].id}/cast")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["role"] == "COACH"
    assert {item["member_id"] for item in body} == {
        str(seeded_data["admin"].id),
        str(seeded_data["regular"].id),
    }


@pytest.mark.asyncio
async def test_create_event_requires_admin(regular_client, seeded_data):
    response = await regular_client.post(
        "/events",
        json={
            "season_id": str(seeded_data['current_season'].id),
            "title": "Nouveau match",
            "event_type": "match",
            "start_at": "2026-04-10T20:00:00",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_event_success(auth_client, seeded_data):
    response = await auth_client.post(
        "/events",
        json={
            "season_id": str(seeded_data['current_season'].id),
            "venue_id": str(seeded_data['venue'].id),
            "title": "Cabaret du vendredi",
            "event_type": "cabaret",
            "start_at": "2026-04-10T20:00:00",
            "end_at": "2026-04-10T22:00:00",
            "visibility": "all",
        },
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Cabaret du vendredi"


@pytest.mark.asyncio
async def test_create_event_validation_returns_422(auth_client, seeded_data):
    response = await auth_client.post(
        "/events",
        json={
            "season_id": str(seeded_data['current_season'].id),
            "title": "Oops",
            "event_type": "invalid",
            "start_at": "2026-04-10T20:00:00",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_event_success(auth_client, seeded_data):
    response = await auth_client.put(
        f"/events/{seeded_data['public_event'].id}",
        json={"title": "Match renommé", "visibility": "admin"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Match renommé"
    assert response.json()["visibility"] == "admin"


@pytest.mark.asyncio
async def test_update_event_not_found(auth_client, seeded_data):
    response = await auth_client.put(
        "/events/00000000-0000-0000-0000-000000000001",
        json={"title": "Ghost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_event_success(auth_client, seeded_data):
    response = await auth_client.delete(f"/events/{seeded_data['public_event'].id}")
    assert response.status_code == 204

    get_response = await auth_client.get(f"/events/{seeded_data['public_event'].id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_event_not_found(auth_client, seeded_data):
    response = await auth_client.delete("/events/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_import_calendar_success_and_skips_duplicates(auth_client, seeded_data):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Date", "Titre", "Lieu", "Notes"])
    ws.append(["10/02/2026 20:00", "Match public", "Maison de quartier", "duplicate"])
    ws.append(["11/04/2026 20:30", "Cabaret spécial", "Maison de quartier", "new"])

    content = BytesIO()
    wb.save(content)
    content.seek(0)

    response = await auth_client.post(
        f"/events/import-calendar?season_id={seeded_data['current_season'].id}",
        files={"file": ("calendar.xlsx", content.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert body["skipped"] == 1


@pytest.mark.asyncio
async def test_import_calendar_requires_admin(regular_client, seeded_data):
    response = await regular_client.post(
        f"/events/import-calendar?season_id={seeded_data['current_season'].id}",
        files={"file": ("calendar.xlsx", b"fake", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 403
