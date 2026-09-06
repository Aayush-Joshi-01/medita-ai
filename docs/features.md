# Features

Each feature is mapped to its backend endpoints and frontend route. Endpoint paths are the
target API surface (prefix `/api`); they are implemented across steps 3–5 of the build.
Status legend: **planned** · **in progress** · **done**.

---

## Authentication & accounts

**Status:** planned

| Concern | Detail |
|---|---|
| Endpoints | `POST /account/register`, `POST /account/login`, `POST /account/refresh`, `GET /account/me` |
| Frontend | `/(auth)/login` |
| Notes | JWT access + refresh tokens; roles `patient` / `doctor`; bcrypt hashing; `SECRET_KEY` required at boot. |

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

**Status:** planned

| Concern | Detail |
|---|---|
| Endpoints | `GET /specialization`, `POST /specialization` |
| Frontend | referenced in profile and doctor listings |
| Notes | Seeded from `backend/seeds/`. |

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
