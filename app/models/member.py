"""Member model."""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Member(Base):
    __tablename__ = "members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # App role
    app_role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="member"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Activation
    activation_token: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    activation_expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Reset password
    reset_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reset_expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now()
    )

    # Relationships
    member_seasons = relationship("MemberSeason", back_populates="member")
    member_commissions = relationship("MemberCommission", back_populates="member")
    show_plans = relationship("ShowPlan", back_populates="created_by_member")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_admin(self) -> bool:
        return self.app_role == "admin"
