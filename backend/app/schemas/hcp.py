from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OnboardingStatus


class HCPProfileCreate(BaseModel):
    license_number: str = Field(min_length=1, max_length=120)
    license_authority: str | None = Field(default=None, max_length=255)
    primary_specialization_id: int
    years_experience: int | None = Field(default=None, ge=0, le=80)
    bio: str | None = None
    consultation_fee: Decimal | None = Field(default=None, ge=0)
    consultation_fee_currency: str = Field(default="USD", min_length=3, max_length=3)
    requested_hospital_id: int | None = None


class HCPProfileUpdate(BaseModel):
    license_number: str | None = Field(default=None, min_length=1, max_length=120)
    license_authority: str | None = Field(default=None, max_length=255)
    primary_specialization_id: int | None = None
    years_experience: int | None = Field(default=None, ge=0, le=80)
    bio: str | None = None
    consultation_fee: Decimal | None = Field(default=None, ge=0)
    consultation_fee_currency: str | None = Field(default=None, min_length=3, max_length=3)
    requested_hospital_id: int | None = None


class HCPProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    license_number: str
    license_authority: str | None
    primary_specialization_id: int
    years_experience: int | None
    bio: str | None
    consultation_fee: Decimal | None
    consultation_fee_currency: str
    requested_hospital_id: int | None
    status: OnboardingStatus
    submitted_at: datetime | None
    reviewed_at: datetime | None
    reviewed_by_user_id: int | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime
