"""Per-hospital admin membership. Deliberately not a `UserRole` value — see
docs/architecture.md and the onboarding plan: hospital-admin-ness is scoped
per hospital and granted automatically on hospital approval, unlike the
global, manually-bootstrapped `platform_admin` role."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class HospitalAdmin(Base):
    __tablename__ = "hospital_admins"

    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
