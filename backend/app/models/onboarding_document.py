"""Polymorphic document uploads for both onboarding flows (owner_type +
owner_id, no DB-level FK on owner_id — a deliberate tradeoff for the shared
shape; integrity is enforced in services/onboarding.py)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import OnboardingOwnerType


class OnboardingDocument(Base):
    __tablename__ = "onboarding_documents"
    __table_args__ = (
        Index("ix_onboarding_documents_owner", "owner_type", "owner_id"),
        Index(
            "ix_onboarding_documents_owner_doc_type",
            "owner_type",
            "owner_id",
            "document_type",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_type: Mapped[OnboardingOwnerType] = mapped_column(
        SAEnum(OnboardingOwnerType, name="onboarding_owner_type", native_enum=True), nullable=False
    )
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
