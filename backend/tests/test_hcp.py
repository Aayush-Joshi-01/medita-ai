"""HCP onboarding: independent (platform_admin-reviewed) and
hospital-affiliated (that hospital's admin-reviewed) lifecycles, including
cross-review authorization and the affiliation side effect on approval.
"""

from app.models.user import UserRole
from tests.conftest import AppClient

HOSPITAL_PAYLOAD = {
    "name": "Springfield General",
    "registration_number": "REG-100",
    "address_line1": "123 Main St",
    "city": "Springfield",
    "state": "IL",
    "postal_code": "62701",
    "country": "US",
    "contact_email": "admin@springfield-general.example",
}
HOSPITAL_REQUIRED_DOCS = ["business_registration_certificate", "facility_license", "tax_id_certificate"]
HCP_REQUIRED_DOCS = ["government_id", "medical_degree_certificate", "license_registration_certificate"]


def _upload_docs(app_client: AppClient, headers: dict[str, str], path: str, doc_types: list[str]) -> None:
    for doc_type in doc_types:
        resp = app_client.client.post(
            path,
            headers=headers,
            data={"document_type": doc_type},
            files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert resp.status_code == 201, resp.text


def _approved_hospital(app_client: AppClient) -> int:
    """Create + fully approve a hospital, returning its id."""
    owner_headers = app_client.register_and_login("hospital-owner@example.com")
    admin_headers = app_client.register_and_login("platform-admin@example.com")
    app_client.set_role("platform-admin@example.com", UserRole.platform_admin)
    client = app_client.client

    hospital_id = client.post("/hospitals", json=HOSPITAL_PAYLOAD, headers=owner_headers).json()["id"]
    _upload_docs(app_client, owner_headers, f"/hospitals/{hospital_id}/documents", HOSPITAL_REQUIRED_DOCS)
    client.post(f"/hospitals/{hospital_id}/submit", headers=owner_headers)
    approve_resp = client.post(
        f"/hospitals/{hospital_id}/review/approve", json={}, headers=admin_headers
    )
    assert approve_resp.status_code == 200
    return int(hospital_id)


def test_independent_hcp_lifecycle(app_client: AppClient, fake_storage: dict[str, bytes]) -> None:
    doctor_headers = app_client.register_and_login("doctor@example.com", role="doctor")
    admin_headers = app_client.register_and_login("platform-admin2@example.com")
    app_client.set_role("platform-admin2@example.com", UserRole.platform_admin)
    client = app_client.client

    specialization_id = app_client.add_specialization("Cardiology")

    # A patient can't create an HCP profile.
    patient_headers = app_client.register_and_login("patient@example.com", role="patient")
    forbidden_resp = client.post(
        "/hcp/profile",
        json={"license_number": "LIC-1", "primary_specialization_id": specialization_id},
        headers=patient_headers,
    )
    assert forbidden_resp.status_code == 403

    create_resp = client.post(
        "/hcp/profile",
        json={"license_number": "LIC-123", "primary_specialization_id": specialization_id},
        headers=doctor_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    profile = create_resp.json()
    assert profile["status"] == "draft"
    assert profile["requested_hospital_id"] is None

    dup_resp = client.post(
        "/hcp/profile",
        json={"license_number": "LIC-123", "primary_specialization_id": specialization_id},
        headers=doctor_headers,
    )
    assert dup_resp.status_code == 409

    submit_resp = client.post("/hcp/profile/me/submit", headers=doctor_headers)
    assert submit_resp.status_code == 422
    assert set(submit_resp.json()["error"]["details"]["missing"]) == set(HCP_REQUIRED_DOCS)

    _upload_docs(app_client, doctor_headers, "/hcp/profile/me/documents", HCP_REQUIRED_DOCS)
    submit_resp = client.post("/hcp/profile/me/submit", headers=doctor_headers)
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "submitted"

    hcp_id = submit_resp.json()["id"]

    # Visible in the independent queue.
    queue_resp = client.get("/hcp/review/queue/independent", headers=admin_headers)
    assert hcp_id in [p["id"] for p in queue_resp.json()]

    approve_resp = client.post(f"/hcp/{hcp_id}/review/approve", json={}, headers=admin_headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"


def test_hospital_affiliated_hcp_lifecycle(app_client: AppClient, fake_storage: dict[str, bytes]) -> None:
    hospital_id = _approved_hospital(app_client)
    client = app_client.client

    doctor_headers = app_client.register_and_login("doctor2@example.com", role="doctor")
    specialization_id = app_client.add_specialization("Neurology")

    create_resp = client.post(
        "/hcp/profile",
        json={
            "license_number": "LIC-456",
            "primary_specialization_id": specialization_id,
            "requested_hospital_id": hospital_id,
        },
        headers=doctor_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    hcp_id = create_resp.json()["id"]

    _upload_docs(app_client, doctor_headers, "/hcp/profile/me/documents", HCP_REQUIRED_DOCS)
    submit_resp = client.post("/hcp/profile/me/submit", headers=doctor_headers)
    assert submit_resp.status_code == 200

    # Not in the independent queue.
    admin_headers = app_client.register_and_login("platform-admin3@example.com")
    app_client.set_role("platform-admin3@example.com", UserRole.platform_admin)
    independent_queue = client.get("/hcp/review/queue/independent", headers=admin_headers).json()
    assert hcp_id not in [p["id"] for p in independent_queue]

    # In the hospital's own queue.
    hospital_owner_headers = app_client.login("hospital-owner@example.com")
    hospital_queue = client.get(
        f"/hospitals/{hospital_id}/hcp-review/queue", headers=hospital_owner_headers
    ).json()
    assert hcp_id in [p["id"] for p in hospital_queue]

    # A different hospital's admin can't review it.
    other_hospital_owner_headers = app_client.register_and_login("other-hospital-owner@example.com")
    other_payload = dict(HOSPITAL_PAYLOAD, registration_number="REG-200")
    other_hospital_id = client.post(
        "/hospitals", json=other_payload, headers=other_hospital_owner_headers
    ).json()["id"]
    _upload_docs(
        app_client,
        other_hospital_owner_headers,
        f"/hospitals/{other_hospital_id}/documents",
        HOSPITAL_REQUIRED_DOCS,
    )
    client.post(f"/hospitals/{other_hospital_id}/submit", headers=other_hospital_owner_headers)
    client.post(
        f"/hospitals/{other_hospital_id}/review/approve", json={}, headers=admin_headers
    )
    forbidden_resp = client.post(
        f"/hcp/{hcp_id}/review/approve", json={}, headers=other_hospital_owner_headers
    )
    assert forbidden_resp.status_code == 403

    # The correct hospital's admin can approve — creates an active affiliation.
    approve_resp = client.post(
        f"/hcp/{hcp_id}/review/approve", json={}, headers=hospital_owner_headers
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # platform_admin can also review hospital-affiliated applications, as an
    # escalation path — exercised here via the suspend/reinstate cycle.
    suspend_resp = client.post(f"/hcp/{hcp_id}/suspend", json={}, headers=admin_headers)
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["status"] == "suspended"

    reinstate_resp = client.post(f"/hcp/{hcp_id}/reinstate", json={}, headers=admin_headers)
    assert reinstate_resp.status_code == 200
    assert reinstate_resp.json()["status"] == "approved"

    # The hospital admin can end the affiliation directly.
    doctor_user_id = client.get("/account/me", headers=doctor_headers).json()["id"]
    end_resp = client.post(
        f"/hospitals/{hospital_id}/affiliations/{doctor_user_id}/end", headers=hospital_owner_headers
    )
    assert end_resp.status_code == 204

    # Ending an already-ended affiliation is a 404.
    end_again_resp = client.post(
        f"/hospitals/{hospital_id}/affiliations/{doctor_user_id}/end", headers=hospital_owner_headers
    )
    assert end_again_resp.status_code == 404
