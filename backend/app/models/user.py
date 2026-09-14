"""Core auth entity. HCP-specific fields live on the separate `HCPProfile`
(step 4, hcp_profile.py) rather than here; patient-doctor relationships
(consulting_doctor_id, etc.) land in step 5 ("domain feature port")."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UserRole(enum.StrEnum):
    patient = "patient"
    doctor = "doctor"
    # Global, manually-bootstrapped role (see CONTRIBUTING.md) — reviews
    # hospital applications and independent HCP applications. Per-hospital
    # admin-ness is deliberately NOT a role; see models/hospital_admin.py.
    platform_admin = "platform_admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=True), nullable=False, default=UserRole.patient
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
