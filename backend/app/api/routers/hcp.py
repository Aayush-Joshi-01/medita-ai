"""HCP (doctor) onboarding: profile CRUD, document upload, submission, and
review (by platform_admin for independent applications, or by the requested
hospital's admin — see services/onboarding.assert_can_review_hcp).

Route ordering matters: `/profile/me/...` and `/review/queue/independent`
are declared before `/{hcp_id}/...` so Starlette doesn't try to match them
as an id first.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_platform_admin, require_role
from app.core.errors import NotFoundError
from app.models.enums import OnboardingOwnerType, OnboardingStatus
from app.models.hcp_profile import HCPProfile
from app.models.user import User, UserRole
from app.schemas.hcp import HCPProfileCreate, HCPProfileRead, HCPProfileUpdate
from app.schemas.onboarding import OnboardingDocumentRead, ReviewNote, ReviewNoteRequired
from app.services import onboarding

router = APIRouter(prefix="/hcp", tags=["hcp"])


def _get_my_profile_or_404(db: Session, user: User) -> HCPProfile:
    profile = db.query(HCPProfile).filter(HCPProfile.user_id == user.id).first()
    if profile is None:
        raise NotFoundError("HCP profile not found")
    return profile


def _get_profile_or_404(db: Session, hcp_id: int) -> HCPProfile:
    profile = db.get(HCPProfile, hcp_id)
    if profile is None:
        raise NotFoundError("HCP profile not found")
    return profile


# ---------------------------------------------------------------------------
# Self-service profile
# ---------------------------------------------------------------------------


@router.post("/profile", response_model=HCPProfileRead, status_code=201)
def create_profile(
    payload: HCPProfileCreate,
    user: User = Depends(require_role(UserRole.doctor)),
    db: Session = Depends(get_db),
) -> HCPProfile:
    return onboarding.create_hcp_profile(db, user, payload.model_dump())


@router.get("/profile/me", response_model=HCPProfileRead)
def get_my_profile(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> HCPProfile:
    return _get_my_profile_or_404(db, user)


@router.patch("/profile/me", response_model=HCPProfileRead)
def update_my_profile(
    payload: HCPProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HCPProfile:
    profile = _get_my_profile_or_404(db, user)
    return onboarding.update_hcp_profile(db, profile, payload.model_dump(exclude_unset=True))


@router.post("/profile/me/submit", response_model=HCPProfileRead)
def submit_my_profile(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> HCPProfile:
    profile = _get_my_profile_or_404(db, user)
    return onboarding.submit_hcp(db, profile, user)


@router.post("/profile/me/reopen", response_model=HCPProfileRead)
def reopen_my_profile(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> HCPProfile:
    profile = _get_my_profile_or_404(db, user)
    return onboarding.reopen_hcp(db, profile, user)


@router.post("/profile/me/documents", response_model=OnboardingDocumentRead, status_code=201)
async def upload_my_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> object:
    profile = _get_my_profile_or_404(db, user)
    data = await file.read()
    return onboarding.upload_document(
        db,
        owner_type=OnboardingOwnerType.hcp,
        owner_id=profile.id,
        document_type=document_type,
        data=data,
        content_type=file.content_type or "application/octet-stream",
        original_filename=file.filename or document_type,
        uploader=user,
        key_prefix=f"onboarding/hcp/{profile.id}/",
    )


@router.get("/profile/me/documents", response_model=list[OnboardingDocumentRead])
def list_my_documents(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[object]:
    profile = _get_my_profile_or_404(db, user)
    return list(onboarding.list_documents(db, OnboardingOwnerType.hcp, profile.id))


@router.delete("/profile/me/documents/{document_id}", status_code=204)
def delete_my_document(
    document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    profile = _get_my_profile_or_404(db, user)
    onboarding.delete_document(db, OnboardingOwnerType.hcp, profile.id, document_id)


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


@router.get("/review/queue/independent", response_model=list[HCPProfileRead])
def independent_review_queue(
    _: User = Depends(require_platform_admin), db: Session = Depends(get_db)
) -> list[HCPProfile]:
    return (
        db.query(HCPProfile)
        .filter(
            HCPProfile.requested_hospital_id.is_(None),
            HCPProfile.status.in_({OnboardingStatus.submitted, OnboardingStatus.under_review}),
        )
        .order_by(HCPProfile.submitted_at)
        .all()
    )


@router.post("/{hcp_id}/review/start", response_model=HCPProfileRead)
def start_review(
    hcp_id: int,
    payload: ReviewNote,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HCPProfile:
    profile = _get_profile_or_404(db, hcp_id)
    return onboarding.review_hcp(db, profile, actor, "start", payload.note)


@router.post("/{hcp_id}/review/approve", response_model=HCPProfileRead)
def approve(
    hcp_id: int,
    payload: ReviewNote,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HCPProfile:
    profile = _get_profile_or_404(db, hcp_id)
    return onboarding.review_hcp(db, profile, actor, "approve", payload.note)


@router.post("/{hcp_id}/review/reject", response_model=HCPProfileRead)
def reject(
    hcp_id: int,
    payload: ReviewNoteRequired,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HCPProfile:
    profile = _get_profile_or_404(db, hcp_id)
    return onboarding.review_hcp(db, profile, actor, "reject", payload.note)


@router.post("/{hcp_id}/review/request-changes", response_model=HCPProfileRead)
def request_changes(
    hcp_id: int,
    payload: ReviewNoteRequired,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HCPProfile:
    profile = _get_profile_or_404(db, hcp_id)
    return onboarding.review_hcp(db, profile, actor, "request-changes", payload.note)


@router.post("/{hcp_id}/suspend", response_model=HCPProfileRead)
def suspend(
    hcp_id: int,
    payload: ReviewNote,
    actor: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> HCPProfile:
    profile = _get_profile_or_404(db, hcp_id)
    return onboarding.suspend_hcp(db, profile, actor, payload.note)


@router.post("/{hcp_id}/reinstate", response_model=HCPProfileRead)
def reinstate(
    hcp_id: int,
    payload: ReviewNote,
    actor: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> HCPProfile:
    profile = _get_profile_or_404(db, hcp_id)
    return onboarding.reinstate_hcp(db, profile, actor, payload.note)
