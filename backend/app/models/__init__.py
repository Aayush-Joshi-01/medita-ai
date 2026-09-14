"""SQLAlchemy models. Import each model module here so it registers with
Base.metadata — required for Alembic autogenerate and for
Base.metadata.create_all() in tests.

One model per file (enums.py holds small enums shared by more than one
model)."""

from app.models.enums import AffiliationStatus, OnboardingOwnerType, OnboardingStatus  # noqa: F401
from app.models.hcp_profile import HCPProfile  # noqa: F401
from app.models.hospital import Hospital  # noqa: F401
from app.models.hospital_admin import HospitalAdmin  # noqa: F401
from app.models.hospital_affiliation import HospitalAffiliation  # noqa: F401
from app.models.onboarding_document import OnboardingDocument  # noqa: F401
from app.models.onboarding_status_event import OnboardingStatusEvent  # noqa: F401
from app.models.specialization import Specialization  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
