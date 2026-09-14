"""Schemas shared by both onboarding flows (documents, review actions, the
audit trail)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OnboardingOwnerType


class OnboardingDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_type: OnboardingOwnerType
    owner_id: int
    document_type: str
    original_filename: str
    content_type: str
    file_size_bytes: int | None
    uploaded_by_user_id: int
    uploaded_at: datetime


class ReviewNote(BaseModel):
    """Optional note — used for approve/suspend/reinstate."""

    note: str | None = Field(default=None, max_length=2000)


class ReviewNoteRequired(BaseModel):
    """Required note — used for reject/request-changes."""

    note: str = Field(min_length=1, max_length=2000)


class OnboardingStatusEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_type: OnboardingOwnerType
    owner_id: int
    from_status: str | None
    to_status: str
    actor_user_id: int
    note: str | None
    created_at: datetime


class MissingDocumentsDetail(BaseModel):
    missing: list[str]
