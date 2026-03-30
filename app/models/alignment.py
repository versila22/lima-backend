"""Alignment, AlignmentEvent, and AlignmentAssignment models."""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Alignment(Base):
    __tablename__ = "alignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("seasons.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # draft | published
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now()
    )

    # Relationships
    season = relationship("Season", back_populates="alignments")
    creator = relationship("Member", foreign_keys=[created_by])
    alignment_events = relationship(
        "AlignmentEvent",
        back_populates="alignment",
        cascade="all, delete-orphan",
    )
    assignments = relationship(
        "AlignmentAssignment",
        back_populates="alignment",
        cascade="all, delete-orphan",
    )


class AlignmentEvent(Base):
    __tablename__ = "alignment_events"

    alignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alignments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    alignment = relationship("Alignment", back_populates="alignment_events")
    event = relationship("Event", back_populates="alignment_events")


class AlignmentAssignment(Base):
    __tablename__ = "alignment_assignments"
    __table_args__ = (
        UniqueConstraint("alignment_id", "event_id", "member_id"),
        Index("idx_alignment_assignments_event", "event_id"),
        Index("idx_alignment_assignments_member", "member_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alignments.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    # JR | DJ | MJ_MC | AR | COACH
    role: Mapped[str] = mapped_column(String(10), nullable=False)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    alignment = relationship("Alignment", back_populates="assignments")
    event = relationship("Event", back_populates="alignment_assignments")
    member = relationship("Member")
