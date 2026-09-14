"""1:1 with `users` where role=doctor. `status` carries the HCP's own
onboarding lifecycle, independent of `User.is_active` (which only gates
login)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import OnboardingStatus


class HCPProfile(Base):
    __tablename__ = "hcp_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    license_number: Mapped[str] = mapped_column(String(120), nullable=False)
    license_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_specialization_id: Mapped[int] = mapped_column(
        ForeignKey("specializations.id"), nullable=False
    )
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    consultation_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    consultation_fee_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    requested_hospital_id: Mapped[int | None] = mapped_column(
        ForeignKey("hospitals.id"), nullable=True, index=True
    )
    status: Mapped[OnboardingStatus] = mapped_column(
        SAEnum(OnboardingStatus, name="onboarding_status", native_enum=True),
        nullable=False,
        default=OnboardingStatus.draft,
        index=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
