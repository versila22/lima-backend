from datetime import datetime

import pytest
from sqlalchemy import delete

from app.models.alignment import AlignmentAssignment, AlignmentEvent
from app.models.event import Event
from scripts import send_reminders


@pytest.mark.asyncio
async def test_get_due_reminders_returns_published_assignments_only(
    seeded_data,
    db_session,
):
    extra_event = Event(
        season_id=seeded_data["current_season"].id,
        venue_id=seeded_data["venue"].id,
        title="Cabaret brouillon",
        event_type="cabaret",
        start_at=datetime(2026, 2, 10, 21, 0),
        visibility="all",
    )
    db_session.add(extra_event)
    await db_session.flush()

    db_session.add(
        AlignmentEvent(
            alignment_id=seeded_data["draft_alignment"].id,
            event_id=extra_event.id,
            sort_order=1,
        )
    )
    db_session.add_all(
        [
            AlignmentAssignment(
                alignment_id=seeded_data["published_alignment"].id,
                event_id=seeded_data["public_event"].id,
                member_id=seeded_data["regular"].id,
                role="JR",
            ),
            AlignmentAssignment(
                alignment_id=seeded_data["draft_alignment"].id,
                event_id=extra_event.id,
                member_id=seeded_data["regular"].id,
                role="DJ",
            ),
        ]
    )
    await db_session.commit()

    reminders = await send_reminders.get_due_reminders(
        db_session,
        now=datetime(2026, 2, 9, 20, 0),
    )

    assert len(reminders) == 1
    assert reminders[0].email == seeded_data["regular"].email
    assert reminders[0].event_title == seeded_data["public_event"].title
    assert reminders[0].role == "JR"


@pytest.mark.asyncio
async def test_send_due_reminders_sends_email_for_each_due_assignment(
    seeded_data,
    db_session,
    monkeypatch,
):
    await db_session.execute(delete(AlignmentAssignment))
    db_session.add(
        AlignmentAssignment(
            alignment_id=seeded_data["published_alignment"].id,
            event_id=seeded_data["public_event"].id,
            member_id=seeded_data["regular"].id,
            role="MJ_MC",
        )
    )
    await db_session.commit()

    calls = []

    async def fake_send_event_reminder_email(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        send_reminders,
        "send_event_reminder_email",
        fake_send_event_reminder_email,
    )

    sent, failed = await send_reminders.send_due_reminders(
        db_session,
        now=datetime(2026, 2, 9, 20, 0),
        base_url="https://lima.example.org",
    )

    assert (sent, failed) == (1, 0)
    assert calls[0]["to"] == seeded_data["regular"].email
    assert calls[0]["first_name"] == seeded_data["regular"].first_name
    assert calls[0]["event_title"] == seeded_data["public_event"].title
    assert calls[0]["role"] == "MJ_MC"
    assert calls[0]["base_url"] == "https://lima.example.org"
