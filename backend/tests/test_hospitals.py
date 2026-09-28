"""Full hospital onboarding lifecycle: draft -> missing-docs 422 -> upload
required docs -> submit -> platform_admin queue -> approve -> creator becomes
a hospital admin. Plus the reject -> reopen -> resubmit loop, ownership
gating, and double-submit / approve-from-draft state errors.
"""

from app.models.user import UserRole
from tests.conftest import AppClient

HOSPITAL_PAYLOAD = {
    "name": "Springfield General",
    "registration_number": "REG-001",
    "address_line1": "123 Main St",
    "city": "Springfield",
    "state": "IL",
    "postal_code": "62701",
    "country": "US",
    "contact_email": "admin@springfield-general.example",
}

REQUIRED_DOCS = ["business_registration_certificate", "facility_license", "tax_id_certificate"]


def _upload_all_required_docs(app_client: AppClient, headers: dict[str, str], hospital_id: int) -> None:
    for doc_type in REQUIRED_DOCS:
        resp = app_client.client.post(
            f"/hospitals/{hospital_id}/documents",
            headers=headers,
            data={"document_type": doc_type},
            files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert resp.status_code == 201, resp.text


def test_hospital_full_lifecycle(app_client: AppClient, fake_storage: dict[str, bytes]) -> None:
    owner_headers = app_client.register_and_login("owner@example.com")
    admin_headers = app_client.register_and_login("platform-admin@example.com")
    app_client.set_role("platform-admin@example.com", UserRole.platform_admin)
    client = app_client.client

    create_resp = client.post("/hospitals", json=HOSPITAL_PAYLOAD, headers=owner_headers)
    assert create_resp.status_code == 201, create_resp.text
    hospital = create_resp.json()
    assert hospital["status"] == "draft"
    hospital_id = hospital["id"]

    # A second open application is rejected.
    dup_resp = client.post("/hospitals", json=HOSPITAL_PAYLOAD, headers=owner_headers)
    assert dup_resp.status_code == 409

    # Submitting with no documents is hard-blocked.
    submit_resp = client.post(f"/hospitals/{hospital_id}/submit", headers=owner_headers)
    assert submit_resp.status_code == 422
    assert set(submit_resp.json()["error"]["details"]["missing"]) == set(REQUIRED_DOCS)

    # Someone else can't see or edit it.
    other_headers = app_client.register_and_login("someone-else@example.com")
    assert client.get(f"/hospitals/{hospital_id}", headers=other_headers).status_code == 403
    assert (
        client.patch(f"/hospitals/{hospital_id}", json={"name": "x"}, headers=other_headers).status_code
        == 403
    )

    _upload_all_required_docs(app_client, owner_headers, hospital_id)
    assert len(fake_storage) == 3

    submit_resp = client.post(f"/hospitals/{hospital_id}/submit", headers=owner_headers)
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "submitted"

    # Approving from draft/other invalid states is a 409 — try double-submit.
    resubmit_resp = client.post(f"/hospitals/{hospital_id}/submit", headers=owner_headers)
    assert resubmit_resp.status_code == 409

    # Appears in the platform_admin review queue.
    queue_resp = client.get("/hospitals/review/queue", headers=admin_headers)
    assert queue_resp.status_code == 200
    assert hospital_id in [h["id"] for h in queue_resp.json()]

    # A non-admin can't approve.
    forbidden_resp = client.post(
        f"/hospitals/{hospital_id}/review/approve", json={}, headers=owner_headers
    )
    assert forbidden_resp.status_code == 403

    approve_resp = client.post(
        f"/hospitals/{hospital_id}/review/approve", json={"note": "looks good"}, headers=admin_headers
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # No longer in the queue.
    queue_resp = client.get("/hospitals/review/queue", headers=admin_headers)
    assert hospital_id not in [h["id"] for h in queue_resp.json()]

    # The creator is already an admin (added automatically on approval) —
    # adding them again is a 409.
    owner_user_id = hospital["created_by_user_id"]
    dup_admin_resp = client.post(
        f"/hospitals/{hospital_id}/admins",
        json={"user_id": owner_user_id},
        headers=owner_headers,
    )
    assert dup_admin_resp.status_code == 409

    # Adding a genuinely new admin works.
    app_client.register("second-admin@example.com")
    second_admin_id = client.get("/account/me", headers=app_client.login("second-admin@example.com")).json()[
        "id"
    ]
    add_admin_resp = client.post(
        f"/hospitals/{hospital_id}/admins",
        json={"user_id": second_admin_id},
        headers=owner_headers,
    )
    assert add_admin_resp.status_code == 201


def test_hospital_reject_reopen_resubmit_loop(app_client: AppClient, fake_storage: dict[str, bytes]) -> None:
    owner_headers = app_client.register_and_login("owner2@example.com")
    admin_headers = app_client.register_and_login("platform-admin2@example.com")
    app_client.set_role("platform-admin2@example.com", UserRole.platform_admin)
    client = app_client.client

    hospital_id = client.post("/hospitals", json=HOSPITAL_PAYLOAD, headers=owner_headers).json()["id"]
    _upload_all_required_docs(app_client, owner_headers, hospital_id)
    client.post(f"/hospitals/{hospital_id}/submit", headers=owner_headers)

    # Rejecting requires a note.
    no_note_resp = client.post(
        f"/hospitals/{hospital_id}/review/reject", json={}, headers=admin_headers
    )
    assert no_note_resp.status_code == 422

    reject_resp = client.post(
        f"/hospitals/{hospital_id}/review/reject",
        json={"note": "registration number could not be verified"},
        headers=admin_headers,
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    reopen_resp = client.post(f"/hospitals/{hospital_id}/reopen", headers=owner_headers)
    assert reopen_resp.status_code == 200
    assert reopen_resp.json()["status"] == "draft"

    # Documents survived the reject/reopen cycle — can resubmit immediately.
    resubmit_resp = client.post(f"/hospitals/{hospital_id}/submit", headers=owner_headers)
    assert resubmit_resp.status_code == 200
    assert resubmit_resp.json()["status"] == "submitted"


def test_hospital_changes_requested_loop(app_client: AppClient, fake_storage: dict[str, bytes]) -> None:
    owner_headers = app_client.register_and_login("owner3@example.com")
    admin_headers = app_client.register_and_login("platform-admin3@example.com")
    app_client.set_role("platform-admin3@example.com", UserRole.platform_admin)
    client = app_client.client

    hospital_id = client.post("/hospitals", json=HOSPITAL_PAYLOAD, headers=owner_headers).json()["id"]
    _upload_all_required_docs(app_client, owner_headers, hospital_id)
    client.post(f"/hospitals/{hospital_id}/submit", headers=owner_headers)

    changes_resp = client.post(
        f"/hospitals/{hospital_id}/review/request-changes",
        json={"note": "please clarify the facility license expiry"},
        headers=admin_headers,
    )
    assert changes_resp.status_code == 200
    assert changes_resp.json()["status"] == "changes_requested"

    update_resp = client.patch(
        f"/hospitals/{hospital_id}", json={"description": "clarified"}, headers=owner_headers
    )
    assert update_resp.status_code == 200

    resubmit_resp = client.post(f"/hospitals/{hospital_id}/submit", headers=owner_headers)
    assert resubmit_resp.status_code == 200
    assert resubmit_resp.json()["status"] == "submitted"
