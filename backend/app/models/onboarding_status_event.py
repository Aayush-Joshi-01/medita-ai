"""Audit trail for every onboarding status transition (both hospitals and
HCPs), written by services/onboarding.py alongside each transition."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import OnboardingOwnerType


class OnboardingStatusEvent(Base):
    __tablename__ = "onboarding_status_events"
    __table_args__ = (
        Index("ix_onboarding_status_events_owner", "owner_type", "owner_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_type: Mapped[OnboardingOwnerType] = mapped_column(
        SAEnum(OnboardingOwnerType, name="onboarding_owner_type", native_enum=True), nullable=False
    )
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
