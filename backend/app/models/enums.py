"""Enums shared across more than one onboarding model (kept out of any single
model file since e.g. OnboardingStatus backs both Hospital.status and
HCPProfile.status)."""

from __future__ import annotations

import enum


class OnboardingStatus(enum.StrEnum):
    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    changes_requested = "changes_requested"
    approved = "approved"
    rejected = "rejected"
    suspended = "suspended"


class OnboardingOwnerType(enum.StrEnum):
    hospital = "hospital"
    hcp = "hcp"


class AffiliationStatus(enum.StrEnum):
    active = "active"
    ended = "ended"
