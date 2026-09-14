# Features

Each feature is mapped to its backend endpoints and frontend route. Endpoint paths are the
target API surface (prefix `/api`); they are implemented across steps 3–6 of the build.
Status legend: **planned** · **in progress** · **done**.

---

## Authentication & accounts

**Status:** done (backend) — frontend wiring lands in step 7

| Concern | Detail |
|---|---|
| Endpoints | `POST /account/register`, `POST /account/login`, `POST /account/refresh`, `GET /account/me` |
| Frontend | `/(auth)/login` |
| Notes | JWT access + refresh tokens; roles `patient` / `doctor` / `platform_admin`; bcrypt hashing; `SECRET_KEY` required at boot (`backend/app/core/security.py`, `backend/app/api/routers/account.py`). |

---

## Hospital onboarding

**Status:** schema done (step 4a) — API + notifications land in step 4b

| Concern | Detail |
|---|---|
| Endpoints | `POST /hospitals`, `GET /hospitals/mine`, `GET /hospitals/{id}`, `PATCH /hospitals/{id}`, `POST /hospitals/{id}/documents` (+ GET/DELETE), `POST /hospitals/{id}/submit`, `GET /hospitals/review/queue` (platform_admin), `POST /hospitals/{id}/review/{start\|approve\|reject\|request-changes}` (platform_admin), `POST /hospitals/{id}/suspend` / `/reinstate` (platform_admin), `POST /hospitals/{id}/reopen`, `POST /hospitals/{id}/admins`, `POST /hospitals/{hospital_id}/affiliations/{user_id}/end`, `GET /hospitals/{hospital_id}/hcp-review/queue` |
| Frontend | hospital application wizard + review queue, part of the future admin/hospital dashboard (step 7) |
| Notes | A hospital's application *is* its record (`hospitals.status`, not a separate application table). Required documents: `business_registration_certificate`, `facility_license`, `tax_id_certificate` — submission is hard-blocked until all three are uploaded. Approval makes the applicant the hospital's first admin (`hospital_admins` row); more admins can be added afterward. See [`docs/architecture.md`](architecture.md) and [`docs/fhir-mapping.md`](fhir-mapping.md#hospitals--organization). |

## HCP (doctor) onboarding

**Status:** schema done (step 4a) — API + notifications land in step 4b

| Concern | Detail |
|---|---|
| Endpoints | `POST /hcp/profile`, `GET /hcp/profile/me`, `PATCH /hcp/profile/me`, `POST /hcp/profile/me/documents` (+ GET/DELETE), `POST /hcp/profile/me/submit`, `POST /hcp/profile/me/reopen`, `GET /hcp/review/queue/independent` (platform_admin), `POST /hcp/{id}/review/{start\|approve\|reject\|request-changes}`, `POST /hcp/{id}/suspend` / `/reinstate` (platform_admin) |
| Frontend | doctor application wizard, part of the future doctor onboarding flow (step 7) |
| Notes | One `hcp_profiles` row per doctor (`users.role = doctor`), independent of `User.is_active` (which only gates login). Hospital affiliation is optional: set `requested_hospital_id` to route review to that hospital's admin(s) instead of `platform_admin`, and approval creates a `hospital_affiliations` row. Required documents: `government_id`, `medical_degree_certificate`, `license_registration_certificate` — submission is hard-blocked until all three are uploaded. See [`docs/architecture.md`](architecture.md) and [`docs/fhir-mapping.md`](fhir-mapping.md#users-role--doctor--practitioner--practitionerrole). |

---

## AI doctor chat

**Status:** planned

| Concern | Detail |
|---|---|
| Endpoints | `GET /ai-doctor` (list specialist personas), `POST /ai-doctor/chat`, `POST /ai-doctor/document_registration`, `POST /ai-doctor/get_context` |
| Frontend | `/(dashboard)/ai-doctor` |
| Services | `services/llm.py` (LiteLLM), `services/rag.py` (Qdrant), `app/prompts/doctors_config/*.yaml` |
| Notes | Personas: cardiology, dermatology, gastroenterology, neurology, general medicine. Optional RAG grounding on the patient's own documents. Persona configs are YAML — adding a specialist is a new file. |

---

## Medical imaging analysis

**Status:** planned

| Concern | Detail |
|---|---|
| Endpoints | `POST /image` (upload + enqueue analysis, returns job), `GET /image` (list), `GET /image/{id}` (status + result), `GET /image/{id}/report` (detailed report), `GET /chat/{image_id}/history`, `POST /chat/{image_id}` (follow-up Q&A) |
| Frontend | `/(dashboard)/imaging` |
| Services | `services/storage.py` (MinIO), `services/llm.py` (vision), arq worker `analyze_image` |
| Notes | Structured report sections: patient information / examination / findings / impression, plus a short summary. Image bytes go to MinIO, never Postgres. |

---

## Consultation transcription & analysis

**Status:** planned

| Concern | Detail |
|---|---|
| Endpoints | `POST /transcribe` (upload recording + enqueue), `POST /analyze` (enqueue structured analysis), `GET /transcripts/{id}` |
| Frontend | `/(dashboard)/video-call` (transcription tab) |
| Services | `services/audio.py` (ffmpeg), `services/transcription.py` (local Whisper / Groq / Deepgram), `services/llm.py`, arq workers `transcribe` + `analyze_transcript` |
| Notes | Analysis extracts symptoms, findings, diagnosis, treatment plan, follow-up, communication-quality assessment, and recommended medications. Authentication required (closed from v2). |

---

## Personal record RAG

**Status:** planned

| Concern | Detail |
|---|---|
| Endpoints | `POST /ai-doctor/document_registration`, `POST /ai-doctor/get_context` |
| Frontend | document upload within `/(dashboard)/ai-doctor` and `/(dashboard)/profile` |
| Services | `services/documents.py` (pymupdf4llm), `services/rag.py` (Qdrant), arq worker `ingest_document` |
| Notes | Per-user isolation via a `user_id` payload filter in Qdrant. `user_knowledge` holds a rolling summary prepended to specialist prompts. |

---

## Doctor–patient management

**Status:** planned

| Concern | Detail |
|---|---|
| Endpoints | `GET /doctor` (list doctors), `POST /doctor/patient-mapping`, `GET /doctor/patients`, `POST /doctor/chat/{patient_id}`, `GET /doctor/chat/{patient_id}/history`, `GET /all_patients` |
| Frontend | `/(dashboard)/chat`, `/(dashboard)/dashboard` |
| Notes | Doctors see only mapped patients. Direct doctor↔patient messaging shares the `chat_history` table with a distinct `chat_context`. |

---

## Appointments

**Status:** planned

| Concern | Detail |
|---|---|
| Endpoints | `POST /appointments`, `GET /appointments`, `PUT /appointments/{id}` |
| Frontend | `/(dashboard)/video-call` (scheduling tab), `/(dashboard)/dashboard` |
| Notes | Status lifecycle: requested → confirmed → completed / cancelled. Mapped to FHIR `Appointment` / `Encounter`. |

---

## Knowledge base

**Status:** planned

| Concern | Detail |
|---|---|
| Endpoints | `GET /knowledge-base`, `POST /knowledge-base`, `GET /knowledge-base/{id}` |
| Frontend | `/(dashboard)/knowledge-base` |
| Notes | Shared articles / case studies authored by doctors. Real persistence (v1/v2 always showed hardcoded samples). |

---

## Specializations

**Status:** table + seed data done (step 4a) — a dedicated `/specialization` listing
endpoint is planned for step 5

| Concern | Detail |
|---|---|
| Endpoints | referenced today by `hcp_profiles.primary_specialization_id`; a standalone `GET /specialization` listing endpoint lands with the doctors directory in step 5 |
| Frontend | referenced in profile and doctor listings |
| Notes | Seeded (cardiology, dermatology, gastroenterology, neurology, general medicine) via `backend/app/seeds/load.py` (`make seed`). |

---

## FHIR interoperability

**Status:** planned

| Concern | Detail |
|---|---|
| Endpoints | `/api/fhir/*` (read + sync), `/fhir/*` (direct HAPI proxy) |
| Services | `services/fhir.py` |
| Notes | See [`fhir-mapping.md`](fhir-mapping.md). Resources: Patient, Practitioner, Appointment, Encounter, DiagnosticReport, Observation, MedicationStatement, DocumentReference. |

---

## Async job tracking

**Status:** planned

| Concern | Detail |
|---|---|
| Endpoints | status embedded in each resource's `GET /{id}` |
| Storage | `processing_status` table |
| Notes | Every AI operation writes a row: `entity_type`, `entity_id`, `status`, `error`, timestamps. Doubles as an audit trail. |
