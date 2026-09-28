"""State machine and business rules for both onboarding flows (hospitals and
HCPs). Routers stay thin (HTTP + validation only); this module owns
transitions, document requirements, and the side effects each transition
triggers. See docs/architecture.md section 9 and docs/features.md.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.models.enums import OnboardingOwnerType, OnboardingStatus
from app.models.hcp_profile import HCPProfile
from app.models.hospital import Hospital
from app.models.hospital_admin import HospitalAdmin
from app.models.hospital_affiliation import HospitalAffiliation
from app.models.onboarding_document import OnboardingDocument
from app.models.onboarding_status_event import OnboardingStatusEvent
from app.models.specialization import Specialization
from app.models.user import User, UserRole
from app.services import notifications, storage

logger = logging.getLogger(__name__)

ALLOWED_UPLOAD_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

REQUIRED_DOCUMENT_TYPES: dict[OnboardingOwnerType, set[str]] = {
    OnboardingOwnerType.hospital: {
        "business_registration_certificate",
        "facility_license",
        "tax_id_certificate",
    },
    OnboardingOwnerType.hcp: {
        "government_id",
        "medical_degree_certificate",
        "license_registration_certificate",
    },
}

# States an owner can submit *from*.
_SUBMITTABLE_FROM = {OnboardingStatus.draft, OnboardingStatus.changes_requested}
# States a reviewer can act *from* (start/approve/reject/request-changes).
_REVIEW_ACTIONABLE_FROM = {OnboardingStatus.submitted, OnboardingStatus.under_review}
# Non-terminal — used to enforce "at most one open application per user".
NON_TERMINAL_STATUSES = {
    OnboardingStatus.draft,
    OnboardingStatus.submitted,
    OnboardingStatus.under_review,
    OnboardingStatus.changes_requested,
}


# ---------------------------------------------------------------------------
# Shared: status events, document requirements, uploads
# ---------------------------------------------------------------------------


def record_status_event(
    db: Session,
    *,
    owner_type: OnboardingOwnerType,
    owner_id: int,
    from_status: str | None,
    to_status: str,
    actor: User,
    note: str | None = None,
) -> OnboardingStatusEvent:
    event = OnboardingStatusEvent(
        owner_type=owner_type,
        owner_id=owner_id,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=actor.id,
        note=note,
    )
    db.add(event)
    return event


def _transition(
    db: Session,
    *,
    owner_type: OnboardingOwnerType,
    entity: Hospital | HCPProfile,
    allowed_from: set[OnboardingStatus],
    to_status: OnboardingStatus,
    actor: User,
    note: str | None = None,
    is_review_decision: bool = False,
) -> None:
    if entity.status not in allowed_from:
        raise ConflictError(
            f"Cannot move from status '{entity.status.value}' to '{to_status.value}'"
        )
    from_status = entity.status.value
    entity.status = to_status
    if is_review_decision:
        entity.reviewed_at = datetime.now(UTC)
        entity.reviewed_by_user_id = actor.id
        entity.review_note = note
    elif to_status == OnboardingStatus.changes_requested:
        entity.review_note = note
    record_status_event(
        db,
        owner_type=owner_type,
        owner_id=entity.id,
        from_status=from_status,
        to_status=to_status.value,
        actor=actor,
        note=note,
    )


def missing_documents(db: Session, owner_type: OnboardingOwnerType, owner_id: int) -> list[str]:
    required = REQUIRED_DOCUMENT_TYPES[owner_type]
    present = {
        row[0]
        for row in db.query(OnboardingDocument.document_type)
        .filter(
            OnboardingDocument.owner_type == owner_type, OnboardingDocument.owner_id == owner_id
        )
        .all()
    }
    return sorted(required - present)


def _validate_upload(
    owner_type: OnboardingOwnerType, document_type: str, content_type: str, size_bytes: int
) -> None:
    if document_type not in REQUIRED_DOCUMENT_TYPES[owner_type]:
        raise UnprocessableError(
            f"Unknown document_type for {owner_type.value}: {document_type}",
            details={"allowed": sorted(REQUIRED_DOCUMENT_TYPES[owner_type])},
        )
    if content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise UnprocessableError(
            f"Unsupported content type: {content_type}",
            details={"allowed": sorted(ALLOWED_UPLOAD_CONTENT_TYPES)},
        )
    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
        raise UnprocessableError("File exceeds the 10MB upload limit")


def upload_document(
    db: Session,
    *,
    owner_type: OnboardingOwnerType,
    owner_id: int,
    document_type: str,
    data: bytes,
    content_type: str,
    original_filename: str,
    uploader: User,
    key_prefix: str,
) -> OnboardingDocument:
    _validate_upload(owner_type, document_type, content_type, len(data))

    existing = (
        db.query(OnboardingDocument)
        .filter(
            OnboardingDocument.owner_type == owner_type,
            OnboardingDocument.owner_id == owner_id,
            OnboardingDocument.document_type == document_type,
        )
        .first()
    )
    if existing is not None:
        try:
            storage.delete_object(settings.minio_docs_bucket, existing.storage_key)
        except Exception:
            logger.warning(
                "Failed to delete replaced document %s", existing.storage_key, exc_info=True
            )
        db.delete(existing)
        db.flush()

    storage_key = storage.put_object(
        settings.minio_docs_bucket, data, content_type=content_type, key_prefix=key_prefix
    )
    document = OnboardingDocument(
        owner_type=owner_type,
        owner_id=owner_id,
        document_type=document_type,
        storage_key=storage_key,
        original_filename=original_filename,
        content_type=content_type,
        file_size_bytes=len(data),
        uploaded_by_user_id=uploader.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def list_documents(
    db: Session, owner_type: OnboardingOwnerType, owner_id: int
) -> list[OnboardingDocument]:
    return (
        db.query(OnboardingDocument)
        .filter(
            OnboardingDocument.owner_type == owner_type, OnboardingDocument.owner_id == owner_id
        )
        .order_by(OnboardingDocument.uploaded_at)
        .all()
    )


def delete_document(
    db: Session, owner_type: OnboardingOwnerType, owner_id: int, document_id: int
) -> None:
    document = (
        db.query(OnboardingDocument)
        .filter(
            OnboardingDocument.id == document_id,
            OnboardingDocument.owner_type == owner_type,
            OnboardingDocument.owner_id == owner_id,
        )
        .first()
    )
    if document is None:
        raise NotFoundError("Document not found")
    try:
        storage.delete_object(settings.minio_docs_bucket, document.storage_key)
    except Exception:
        logger.warning("Failed to delete document %s", document.storage_key, exc_info=True)
    db.delete(document)
    db.commit()


# ---------------------------------------------------------------------------
# Hospitals
# ---------------------------------------------------------------------------


def create_hospital(db: Session, creator: User, data: dict[str, object]) -> Hospital:
    existing = (
        db.query(Hospital)
        .filter(
            Hospital.created_by_user_id == creator.id, Hospital.status.in_(NON_TERMINAL_STATUSES)
        )
        .first()
    )
    if existing is not None:
        raise ConflictError("You already have an open hospital application")

    hospital = Hospital(**data, created_by_user_id=creator.id, status=OnboardingStatus.draft)
    db.add(hospital)
    db.flush()
    record_status_event(
        db,
        owner_type=OnboardingOwnerType.hospital,
        owner_id=hospital.id,
        from_status=None,
        to_status=OnboardingStatus.draft.value,
        actor=creator,
    )
    db.commit()
    db.refresh(hospital)
    return hospital


def update_hospital(db: Session, hospital: Hospital, data: dict[str, object]) -> Hospital:
    if hospital.status not in _SUBMITTABLE_FROM:
        raise ConflictError(f"Cannot edit an application in status '{hospital.status.value}'")
    for field, value in data.items():
        setattr(hospital, field, value)
    db.commit()
    db.refresh(hospital)
    return hospital


def submit_hospital(db: Session, hospital: Hospital, actor: User) -> Hospital:
    missing = missing_documents(db, OnboardingOwnerType.hospital, hospital.id)
    if missing:
        raise UnprocessableError("Required documents are missing", details={"missing": missing})
    _transition(
        db,
        owner_type=OnboardingOwnerType.hospital,
        entity=hospital,
        allowed_from=_SUBMITTABLE_FROM,
        to_status=OnboardingStatus.submitted,
        actor=actor,
    )
    hospital.submitted_at = datetime.now(UTC)
    db.commit()
    db.refresh(hospital)
    notifications.notify_status_change(
        owner_label=f"Hospital application: {hospital.name}",
        recipient_email=hospital.contact_email,
        to_status="submitted",
    )
    return hospital


def review_hospital(
    db: Session, hospital: Hospital, actor: User, action: str, note: str | None
) -> Hospital:
    if action == "start":
        _transition(
            db,
            owner_type=OnboardingOwnerType.hospital,
            entity=hospital,
            allowed_from=_REVIEW_ACTIONABLE_FROM,
            to_status=OnboardingStatus.under_review,
            actor=actor,
            note=note,
        )
    elif action == "approve":
        _transition(
            db,
            owner_type=OnboardingOwnerType.hospital,
            entity=hospital,
            allowed_from=_REVIEW_ACTIONABLE_FROM,
            to_status=OnboardingStatus.approved,
            actor=actor,
            note=note,
            is_review_decision=True,
        )
        db.flush()
        already_admin = (
            db.query(HospitalAdmin)
            .filter_by(hospital_id=hospital.id, user_id=hospital.created_by_user_id)
            .first()
        )
        if already_admin is None:
            db.add(HospitalAdmin(hospital_id=hospital.id, user_id=hospital.created_by_user_id))
    elif action == "reject":
        _transition(
            db,
            owner_type=OnboardingOwnerType.hospital,
            entity=hospital,
            allowed_from=_REVIEW_ACTIONABLE_FROM,
            to_status=OnboardingStatus.rejected,
            actor=actor,
            note=note,
            is_review_decision=True,
        )
    elif action == "request-changes":
        _transition(
            db,
            owner_type=OnboardingOwnerType.hospital,
            entity=hospital,
            allowed_from=_REVIEW_ACTIONABLE_FROM,
            to_status=OnboardingStatus.changes_requested,
            actor=actor,
            note=note,
        )
    else:
        raise ValueError(f"Unsupported review action: {action}")

    db.commit()
    db.refresh(hospital)
    notifications.notify_status_change(
        owner_label=f"Hospital application: {hospital.name}",
        recipient_email=hospital.contact_email,
        to_status=hospital.status.value,
        note=note,
    )
    return hospital


def reopen_hospital(db: Session, hospital: Hospital, actor: User) -> Hospital:
    _transition(
        db,
        owner_type=OnboardingOwnerType.hospital,
        entity=hospital,
        allowed_from={OnboardingStatus.rejected},
        to_status=OnboardingStatus.draft,
        actor=actor,
    )
    db.commit()
    db.refresh(hospital)
    return hospital


def suspend_hospital(db: Session, hospital: Hospital, actor: User, note: str | None) -> Hospital:
    _transition(
        db,
        owner_type=OnboardingOwnerType.hospital,
        entity=hospital,
        allowed_from={OnboardingStatus.approved},
        to_status=OnboardingStatus.suspended,
        actor=actor,
        note=note,
    )
    db.commit()
    db.refresh(hospital)
    notifications.notify_status_change(
        owner_label=f"Hospital application: {hospital.name}",
        recipient_email=hospital.contact_email,
        to_status="suspended",
        note=note,
    )
    return hospital


def reinstate_hospital(db: Session, hospital: Hospital, actor: User, note: str | None) -> Hospital:
    _transition(
        db,
        owner_type=OnboardingOwnerType.hospital,
        entity=hospital,
        allowed_from={OnboardingStatus.suspended},
        to_status=OnboardingStatus.approved,
        actor=actor,
        note=note,
    )
    db.commit()
    db.refresh(hospital)
    notifications.notify_status_change(
        owner_label=f"Hospital application: {hospital.name}",
        recipient_email=hospital.contact_email,
        to_status="approved",
        note=note,
    )
    return hospital


def add_hospital_admin(db: Session, hospital: Hospital, new_admin_user_id: int) -> HospitalAdmin:
    if hospital.status != OnboardingStatus.approved:
        raise ConflictError("Hospital must be approved to have admins")
    user = db.get(User, new_admin_user_id)
    if user is None:
        raise NotFoundError("User not found")
    existing = (
        db.query(HospitalAdmin)
        .filter_by(hospital_id=hospital.id, user_id=new_admin_user_id)
        .first()
    )
    if existing is not None:
        raise ConflictError("User is already an admin of this hospital")
    admin = HospitalAdmin(hospital_id=hospital.id, user_id=new_admin_user_id)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def _create_active_affiliation(
    db: Session, *, hospital_id: int, user_id: int, actor: User
) -> HospitalAffiliation:
    existing = (
        db.query(HospitalAffiliation)
        .filter_by(hospital_id=hospital_id, user_id=user_id, status="active")
        .first()
    )
    if existing is not None:
        raise ConflictError("An active affiliation with this hospital already exists")
    affiliation = HospitalAffiliation(
        hospital_id=hospital_id, user_id=user_id, status="active", created_by_user_id=actor.id
    )
    db.add(affiliation)
    return affiliation


def end_affiliation(db: Session, hospital_id: int, user_id: int) -> HospitalAffiliation:
    affiliation = (
        db.query(HospitalAffiliation)
        .filter_by(hospital_id=hospital_id, user_id=user_id, status="active")
        .first()
    )
    if affiliation is None:
        raise NotFoundError("No active affiliation found")
    affiliation.status = "ended"
    affiliation.ended_at = datetime.now(UTC)
    db.commit()
    db.refresh(affiliation)
    return affiliation


# ---------------------------------------------------------------------------
# HCPs
# ---------------------------------------------------------------------------


def _assert_hospital_approved(db: Session, hospital_id: int) -> None:
    hospital = db.get(Hospital, hospital_id)
    if hospital is None or hospital.status != OnboardingStatus.approved:
        raise UnprocessableError("requested_hospital_id must reference an approved hospital")


def create_hcp_profile(db: Session, user: User, data: dict[str, object]) -> HCPProfile:
    existing = db.query(HCPProfile).filter(HCPProfile.user_id == user.id).first()
    if existing is not None:
        raise ConflictError("An HCP profile already exists for this account")

    requested_hospital_id = data.get("requested_hospital_id")
    if requested_hospital_id is not None:
        _assert_hospital_approved(db, requested_hospital_id)  # type: ignore[arg-type]

    if db.get(Specialization, data["primary_specialization_id"]) is None:
        raise UnprocessableError("Unknown primary_specialization_id")

    profile = HCPProfile(**data, user_id=user.id, status=OnboardingStatus.draft)
    db.add(profile)
    db.flush()
    record_status_event(
        db,
        owner_type=OnboardingOwnerType.hcp,
        owner_id=profile.id,
        from_status=None,
        to_status=OnboardingStatus.draft.value,
        actor=user,
    )
    db.commit()
    db.refresh(profile)
    return profile


def update_hcp_profile(db: Session, profile: HCPProfile, data: dict[str, object]) -> HCPProfile:
    if profile.status not in _SUBMITTABLE_FROM:
        raise ConflictError(f"Cannot edit a profile in status '{profile.status.value}'")
    if "requested_hospital_id" in data and data["requested_hospital_id"] is not None:
        _assert_hospital_approved(db, data["requested_hospital_id"])  # type: ignore[arg-type]
    if "primary_specialization_id" in data:
        if db.get(Specialization, data["primary_specialization_id"]) is None:
            raise UnprocessableError("Unknown primary_specialization_id")
    for field, value in data.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


def submit_hcp(db: Session, profile: HCPProfile, actor: User) -> HCPProfile:
    if profile.requested_hospital_id is not None:
        _assert_hospital_approved(db, profile.requested_hospital_id)
    missing = missing_documents(db, OnboardingOwnerType.hcp, profile.id)
    if missing:
        raise UnprocessableError("Required documents are missing", details={"missing": missing})
    _transition(
        db,
        owner_type=OnboardingOwnerType.hcp,
        entity=profile,
        allowed_from=_SUBMITTABLE_FROM,
        to_status=OnboardingStatus.submitted,
        actor=actor,
    )
    profile.submitted_at = datetime.now(UTC)
    db.commit()
    db.refresh(profile)
    _notify_hcp(db, profile, to_status="submitted")
    return profile


def assert_can_review_hcp(db: Session, user: User, profile: HCPProfile) -> None:
    if profile.requested_hospital_id is None:
        if user.role != UserRole.platform_admin:
            raise ForbiddenError("Only a platform admin can review an independent HCP application")
        return
    is_hospital_admin = (
        db.query(HospitalAdmin)
        .filter_by(hospital_id=profile.requested_hospital_id, user_id=user.id)
        .first()
        is not None
    )
    if not (is_hospital_admin or user.role == UserRole.platform_admin):
        raise ForbiddenError("You are not authorized to review this application")


def review_hcp(
    db: Session, profile: HCPProfile, actor: User, action: str, note: str | None
) -> HCPProfile:
    assert_can_review_hcp(db, actor, profile)

    if action == "start":
        _transition(
            db,
            owner_type=OnboardingOwnerType.hcp,
            entity=profile,
            allowed_from=_REVIEW_ACTIONABLE_FROM,
            to_status=OnboardingStatus.under_review,
            actor=actor,
            note=note,
        )
    elif action == "approve":
        _transition(
            db,
            owner_type=OnboardingOwnerType.hcp,
            entity=profile,
            allowed_from=_REVIEW_ACTIONABLE_FROM,
            to_status=OnboardingStatus.approved,
            actor=actor,
            note=note,
            is_review_decision=True,
        )
        db.flush()
        if profile.requested_hospital_id is not None:
            _create_active_affiliation(
                db, hospital_id=profile.requested_hospital_id, user_id=profile.user_id, actor=actor
            )
    elif action == "reject":
        _transition(
            db,
            owner_type=OnboardingOwnerType.hcp,
            entity=profile,
            allowed_from=_REVIEW_ACTIONABLE_FROM,
            to_status=OnboardingStatus.rejected,
            actor=actor,
            note=note,
            is_review_decision=True,
        )
    elif action == "request-changes":
        _transition(
            db,
            owner_type=OnboardingOwnerType.hcp,
            entity=profile,
            allowed_from=_REVIEW_ACTIONABLE_FROM,
            to_status=OnboardingStatus.changes_requested,
            actor=actor,
            note=note,
        )
    else:
        raise ValueError(f"Unsupported review action: {action}")

    db.commit()
    db.refresh(profile)
    _notify_hcp(db, profile, to_status=profile.status.value, note=note)
    return profile


def reopen_hcp(db: Session, profile: HCPProfile, actor: User) -> HCPProfile:
    _transition(
        db,
        owner_type=OnboardingOwnerType.hcp,
        entity=profile,
        allowed_from={OnboardingStatus.rejected},
        to_status=OnboardingStatus.draft,
        actor=actor,
    )
    db.commit()
    db.refresh(profile)
    return profile


def suspend_hcp(db: Session, profile: HCPProfile, actor: User, note: str | None) -> HCPProfile:
    _transition(
        db,
        owner_type=OnboardingOwnerType.hcp,
        entity=profile,
        allowed_from={OnboardingStatus.approved},
        to_status=OnboardingStatus.suspended,
        actor=actor,
        note=note,
    )
    db.commit()
    db.refresh(profile)
    _notify_hcp(db, profile, to_status="suspended", note=note)
    return profile


def reinstate_hcp(db: Session, profile: HCPProfile, actor: User, note: str | None) -> HCPProfile:
    _transition(
        db,
        owner_type=OnboardingOwnerType.hcp,
        entity=profile,
        allowed_from={OnboardingStatus.suspended},
        to_status=OnboardingStatus.approved,
        actor=actor,
        note=note,
    )
    db.commit()
    db.refresh(profile)
    _notify_hcp(db, profile, to_status="approved", note=note)
    return profile


def _notify_hcp(
    db: Session, profile: HCPProfile, *, to_status: str, note: str | None = None
) -> None:
    user = db.get(User, profile.user_id)
    if user is None:
        return
    notifications.notify_status_change(
        owner_label=f"HCP profile: {user.full_name}",
        recipient_email=user.email,
        to_status=to_status,
        note=note,
    )
