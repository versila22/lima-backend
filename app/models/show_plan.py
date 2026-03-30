"""ShowPlan model — plans de spectacle."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ShowPlan(Base):
    __tablename__ = "show_plans"
    __table_args__ = (Index("idx_show_plans_event", "event_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # match | cabaret | catch | other
    show_type: Mapped[str] = mapped_column(String(30), nullable=False)
    theme: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    duration: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    venue_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    venue_contact: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Flexible JSON config (players, teams, DJ count, constraints…)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Generated markdown plan
    generated_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now()
    )

    # Relationships
    event = relationship("Event", back_populates="show_plans")
    created_by_member = relationship("Member", back_populates="show_plans")
