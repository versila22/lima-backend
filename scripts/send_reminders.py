"""Send reminder emails for members assigned to events happening in the next 24 hours."""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.alignment import Alignment, AlignmentAssignment
from app.models.event import Event
from app.models.member import Member
from app.models.venue import Venue
from app.services.email_service import send_event_reminder_email

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReminderRecipient:
    email: str
    first_name: str
    event_title: str
    event_date: str
    role: str
    venue_name: str | None
    event_id: str
    member_id: str


def _format_event_date(start_at: datetime) -> str:
    return start_at.strftime("%d/%m/%Y à %H:%M")


def build_reminders_query(window_start: datetime, window_end: datetime) -> Select:
    return (
        select(
            Member.id,
            Member.email,
            Member.first_name,
            Event.id,
            Event.title,
            Event.start_at,
            AlignmentAssignment.role,
            Venue.name,
        )
        .join(AlignmentAssignment, AlignmentAssignment.member_id == Member.id)
        .join(Event, Event.id == AlignmentAssignment.event_id)
        .join(Alignment, Alignment.id == AlignmentAssignment.alignment_id)
        .outerjoin(Venue, Venue.id == Event.venue_id)
        .where(Member.is_active.is_(True))
        .where(Member.email.is_not(None))
        .where(Alignment.status == "published")
        .where(Event.start_at >= window_start)
        .where(Event.start_at <= window_end)
        .order_by(Event.start_at.asc(), Member.last_name.asc(), Member.first_name.asc())
    )


async def get_due_reminders(
    db: AsyncSession,
    now: datetime | None = None,
) -> list[ReminderRecipient]:
    current_time = now or datetime.now(UTC).replace(tzinfo=None)
    window_end = current_time + timedelta(hours=24)

    rows = (await db.execute(build_reminders_query(current_time, window_end))).all()

    reminders: list[ReminderRecipient] = []
    seen: set[tuple[str, str, str]] = set()

    for member_id, email, first_name, event_id, title, start_at, role, venue_name in rows:
        if not email:
            continue

        dedupe_key = (str(event_id), str(member_id), role)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        reminders.append(
            ReminderRecipient(
                email=email,
                first_name=first_name,
                event_title=title,
                event_date=_format_event_date(start_at),
                role=role,
                venue_name=venue_name,
                event_id=str(event_id),
                member_id=str(member_id),
            )
        )

    return reminders


async def send_due_reminders(
    db: AsyncSession,
    now: datetime | None = None,
    base_url: str | None = None,
) -> tuple[int, int]:
    reminders = await get_due_reminders(db=db, now=now)
    frontend_url = (base_url or settings.FRONTEND_URL).rstrip("/")

    sent = 0
    failed = 0

    for reminder in reminders:
        try:
            await send_event_reminder_email(
                to=reminder.email,
                first_name=reminder.first_name,
                event_title=reminder.event_title,
                event_date=reminder.event_date,
                role=reminder.role,
                venue_name=reminder.venue_name,
                base_url=frontend_url,
            )
            sent += 1
            logger.info(
                "Reminder sent to %s for %s (%s)",
                reminder.email,
                reminder.event_title,
                reminder.role,
            )
        except Exception:
            failed += 1
            logger.exception(
                "Reminder failed for %s on event %s",
                reminder.email,
                reminder.event_id,
            )

    logger.info("Reminder run complete: %s sent, %s failed", sent, failed)
    return sent, failed


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await send_due_reminders(db)


if __name__ == "__main__":
    asyncio.run(main())
