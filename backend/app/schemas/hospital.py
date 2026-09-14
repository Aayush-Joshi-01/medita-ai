from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import OnboardingStatus


class HospitalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    registration_number: str = Field(min_length=1, max_length=120)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=120)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str = Field(min_length=2, max_length=2)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=30)
    website: str | None = Field(default=None, max_length=255)
    description: str | None = None


class HospitalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    registration_number: str | None = Field(default=None, min_length=1, max_length=120)
    address_line1: str | None = Field(default=None, min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    state: str | None = Field(default=None, min_length=1, max_length=120)
    postal_code: str | None = Field(default=None, min_length=1, max_length=20)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=30)
    website: str | None = Field(default=None, max_length=255)
    description: str | None = None


class HospitalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    registration_number: str
    address_line1: str
    address_line2: str | None
    city: str
    state: str
    postal_code: str
    country: str
    contact_email: EmailStr
    contact_phone: str | None
    website: str | None
    description: str | None
    status: OnboardingStatus
    created_by_user_id: int
    submitted_at: datetime | None
    reviewed_at: datetime | None
    reviewed_by_user_id: int | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime


class HospitalAdminAdd(BaseModel):
    user_id: int
