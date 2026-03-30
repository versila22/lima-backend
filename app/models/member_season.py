"""MemberSeason model — inscription par saison."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DECIMAL, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MemberSeason(Base):
    __tablename__ = "member_seasons"
    __table_args__ = (UniqueConstraint("member_id", "season_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("seasons.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Player status: M (Match) | C (Cabaret) | L (Loisir) | A (Adhérent)
    player_status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="A"
    )

    # Cotisation HelloAsso
    membership_fee: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(6, 2), nullable=True
    )
    player_fee: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(6, 2), nullable=True
    )
    helloasso_ref: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )

    # Rôle asso
    asso_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    member = relationship("Member", back_populates="member_seasons")
    season = relationship("Season", back_populates="member_seasons")
