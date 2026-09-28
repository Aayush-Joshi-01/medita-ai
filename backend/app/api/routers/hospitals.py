"""Hospital onboarding: application CRUD, document upload, submission,
platform_admin review, and per-hospital admin actions (adding admins, ending
an HCP affiliation, reviewing HCP applications that requested this hospital).

Route ordering matters: static paths (`/mine`, `/review/queue`) are declared
before `/{hospital_id}` so Starlette doesn't try to match them as an id
first — see the module test in tests/test_hospitals.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_hospital_admin, require_platform_admin
from app.core.errors import ForbiddenError, NotFoundError
from app.models.enums import OnboardingOwnerType, OnboardingStatus
from app.models.hcp_profile import HCPProfile
from app.models.hospital import Hospital
from app.models.hospital_admin import HospitalAdmin
from app.models.user import User, UserRole
from app.schemas.hcp import HCPProfileRead
from app.schemas.hospital import HospitalAdminAdd, HospitalCreate, HospitalRead, HospitalUpdate
from app.schemas.onboarding import OnboardingDocumentRead, ReviewNote, ReviewNoteRequired
from app.services import onboarding

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


def _get_hospital_or_404(db: Session, hospital_id: int) -> Hospital:
    hospital = db.get(Hospital, hospital_id)
    if hospital is None:
        raise NotFoundError("Hospital not found")
    return hospital


def _assert_can_view(db: Session, user: User, hospital: Hospital) -> None:
    if user.id == hospital.created_by_user_id or user.role == UserRole.platform_admin:
        return
    is_admin = (
        db.query(HospitalAdmin).filter_by(hospital_id=hospital.id, user_id=user.id).first()
        is not None
    )
    if not is_admin:
        raise ForbiddenError("You do not have access to this hospital")


def _assert_is_owner(user: User, hospital: Hospital) -> None:
    if user.id != hospital.created_by_user_id:
        raise ForbiddenError("Only the applicant may perform this action")


# ---------------------------------------------------------------------------
# Create / list
# ---------------------------------------------------------------------------


@router.post("", response_model=HospitalRead, status_code=201)
def create_hospital(
    payload: HospitalCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Hospital:
    return onboarding.create_hospital(db, user, payload.model_dump())


@router.get("/mine", response_model=list[HospitalRead])
def list_my_hospitals(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Hospital]:
    return (
        db.query(Hospital)
        .filter(Hospital.created_by_user_id == user.id)
        .order_by(Hospital.created_at.desc())
        .all()
    )


@router.get("/review/queue", response_model=list[HospitalRead])
def review_queue(
    _: User = Depends(require_platform_admin), db: Session = Depends(get_db)
) -> list[Hospital]:
    return (
        db.query(Hospital)
        .filter(Hospital.status.in_({OnboardingStatus.submitted, OnboardingStatus.under_review}))
        .order_by(Hospital.submitted_at)
        .all()
    )


# ---------------------------------------------------------------------------
# Single hospital
# ---------------------------------------------------------------------------


@router.get("/{hospital_id}", response_model=HospitalRead)
def get_hospital(
    hospital_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Hospital:
    hospital = _get_hospital_or_404(db, hospital_id)
    _assert_can_view(db, user, hospital)
    return hospital


@router.patch("/{hospital_id}", response_model=HospitalRead)
def update_hospital(
    hospital_id: int,
    payload: HospitalUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Hospital:
    hospital = _get_hospital_or_404(db, hospital_id)
    _assert_is_owner(user, hospital)
    return onboarding.update_hospital(db, hospital, payload.model_dump(exclude_unset=True))


@router.post("/{hospital_id}/submit", response_model=HospitalRead)
def submit_hospital(
    hospital_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Hospital:
    hospital = _get_hospital_or_404(db, hospital_id)
    _assert_is_owner(user, hospital)
    return onboarding.submit_hospital(db, hospital, user)


@router.post("/{hospital_id}/reopen", response_model=HospitalRead)
def reopen_hospital(
    hospital_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Hospital:
    hospital = _get_hospital_or_404(db, hospital_id)
    _assert_is_owner(user, hospital)
    return onboarding.reopen_hospital(db, hospital, user)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@router.post("/{hospital_id}/documents", response_model=OnboardingDocumentRead, status_code=201)
async def upload_hospital_document(
    hospital_id: int,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> object:
    hospital = _get_hospital_or_404(db, hospital_id)
    _assert_is_owner(user, hospital)
    data = await file.read()
    return onboarding.upload_document(
        db,
        owner_type=OnboardingOwnerType.hospital,
        owner_id=hospital.id,
        document_type=document_type,
        data=data,
        content_type=file.content_type or "application/octet-stream",
        original_filename=file.filename or document_type,
        uploader=user,
        key_prefix=f"onboarding/hospital/{hospital.id}/",
    )


@router.get("/{hospital_id}/documents", response_model=list[OnboardingDocumentRead])
def list_hospital_documents(
    hospital_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[object]:
    hospital = _get_hospital_or_404(db, hospital_id)
    _assert_can_view(db, user, hospital)
    return list(onboarding.list_documents(db, OnboardingOwnerType.hospital, hospital.id))


@router.delete("/{hospital_id}/documents/{document_id}", status_code=204)
def delete_hospital_document(
    hospital_id: int,
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    hospital = _get_hospital_or_404(db, hospital_id)
    _assert_is_owner(user, hospital)
    onboarding.delete_document(db, OnboardingOwnerType.hospital, hospital.id, document_id)


# ---------------------------------------------------------------------------
# Platform-admin review
# ---------------------------------------------------------------------------


@router.post("/{hospital_id}/review/start", response_model=HospitalRead)
def start_review(
    hospital_id: int,
    payload: ReviewNote,
    actor: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> Hospital:
    hospital = _get_hospital_or_404(db, hospital_id)
    return onboarding.review_hospital(db, hospital, actor, "start", payload.note)


@router.post("/{hospital_id}/review/approve", response_model=HospitalRead)
def approve(
    hospital_id: int,
    payload: ReviewNote,
    actor: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> Hospital:
    hospital = _get_hospital_or_404(db, hospital_id)
    return onboarding.review_hospital(db, hospital, actor, "approve", payload.note)


@router.post("/{hospital_id}/review/reject", response_model=HospitalRead)
def reject(
    hospital_id: int,
    payload: ReviewNoteRequired,
    actor: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> Hospital:
    hospital = _get_hospital_or_404(db, hospital_id)
    return onboarding.review_hospital(db, hospital, actor, "reject", payload.note)


@router.post("/{hospital_id}/review/request-changes", response_model=HospitalRead)
def request_changes(
    hospital_id: int,
    payload: ReviewNoteRequired,
    actor: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> Hospital:
    hospital = _get_hospital_or_404(db, hospital_id)
    return onboarding.review_hospital(db, hospital, actor, "request-changes", payload.note)


@router.post("/{hospital_id}/suspend", response_model=HospitalRead)
def suspend(
    hospital_id: int,
    payload: ReviewNote,
    actor: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> Hospital:
    hospital = _get_hospital_or_404(db, hospital_id)
    return onboarding.suspend_hospital(db, hospital, actor, payload.note)


@router.post("/{hospital_id}/reinstate", response_model=HospitalRead)
def reinstate(
    hospital_id: int,
    payload: ReviewNote,
    actor: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> Hospital:
    hospital = _get_hospital_or_404(db, hospital_id)
    return onboarding.reinstate_hospital(db, hospital, actor, payload.note)


# ---------------------------------------------------------------------------
# Hospital-admin actions
# ---------------------------------------------------------------------------


@router.post("/{hospital_id}/admins", status_code=201)
def add_admin(
    hospital_id: int,
    payload: HospitalAdminAdd,
    _: User = Depends(require_hospital_admin),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    hospital = _get_hospital_or_404(db, hospital_id)
    admin = onboarding.add_hospital_admin(db, hospital, payload.user_id)
    return {"hospital_id": admin.hospital_id, "user_id": admin.user_id}


@router.post("/{hospital_id}/affiliations/{user_id}/end", status_code=204)
def end_affiliation(
    hospital_id: int,
    user_id: int,
    _: User = Depends(require_hospital_admin),
    db: Session = Depends(get_db),
) -> None:
    onboarding.end_affiliation(db, hospital_id, user_id)


@router.get("/{hospital_id}/hcp-review/queue", response_model=list[HCPProfileRead])
def hcp_review_queue(
    hospital_id: int,
    _: User = Depends(require_hospital_admin),
    db: Session = Depends(get_db),
) -> list[HCPProfile]:
    return (
        db.query(HCPProfile)
        .filter(
            HCPProfile.requested_hospital_id == hospital_id,
            HCPProfile.status.in_({OnboardingStatus.submitted, OnboardingStatus.under_review}),
        )
        .order_by(HCPProfile.submitted_at)
        .all()
    )
