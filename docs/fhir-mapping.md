# FHIR mapping

medita-ai stores clinical data in its own relational schema and exposes it as **FHIR R4**
through an embedded HAPI FHIR server. This document defines the mapping between internal
tables and FHIR resources. It is the contract that `backend/app/services/fhir.py` implements.

FHIR version: **R4 (4.0.1)**. Base URL for direct access: `/fhir`. Application-mediated
access: `/api/fhir`.

---

## Identifier strategy

Every synced resource carries a stable business identifier so internal rows and FHIR
resources can be reconciled:

```
system: https://medita.ai/fhir/identifier/<entity>
value:  <internal primary key>
```

Example: a patient with internal `users.id = 42` →
`Patient.identifier = [{ system: "https://medita.ai/fhir/identifier/user", value: "42" }]`.

---

## Resource map

### `users` (role = patient) → `Patient`

| Internal field | FHIR path |
|---|---|
| `id` | `identifier` (see above) |
| `full_name` | `name[0].text` |
| `email` | `telecom[?system=email].value` |
| `phone` | `telecom[?system=phone].value` |
| `date_of_birth` | `birthDate` |
| `gender` | `gender` |
| `consulting_doctor_id` | `generalPractitioner[0]` → reference to `Practitioner` |

### `users` (role = doctor) → `Practitioner` (+ `PractitionerRole`)

| Internal field | FHIR path |
|---|---|
| `id` | `Practitioner.identifier` |
| `full_name` | `Practitioner.name[0].text` |
| `email` / `phone` | `Practitioner.telecom` |
| `hcp_profiles.primary_specialization_id` | `PractitionerRole.specialty[0]` (coded) |

One `PractitionerRole` is emitted per **active** `hospital_affiliations` row for that
practitioner (see below) — a doctor affiliated with two hospitals yields two
`PractitionerRole` resources, one per `organization`. An independent HCP (no active
affiliation) still gets a single `PractitionerRole`, with no `organization` reference. Only
`hcp_profiles.status = approved` practitioners are synced at all.

### `specializations` → coded concept

Used as `PractitionerRole.specialty` and `Encounter.type`. System:
`https://medita.ai/fhir/CodeSystem/specialization`.

### `hospitals` → `Organization`

| Internal field | FHIR path |
|---|---|
| `id` | `Organization.identifier[0]` (system `.../identifier/hospital`) |
| `registration_number` | `Organization.identifier[1]` (system `.../identifier/hospital-registration`) |
| `name` | `Organization.name` |
| `address_line1`/`address_line2`, `city`, `state`, `postal_code`, `country` | `Organization.address[0]` |
| `contact_email` | `Organization.telecom[?system=email]` |
| `contact_phone` | `Organization.telecom[?system=phone]` |
| `status = approved` | `Organization.active = true`; any other status → not yet synced (no resource), or `active = false` if a previously-approved hospital is later `suspended` |

### `hospital_affiliations` (status = `active`) → `PractitionerRole.organization`

Not a resource of its own — it's the join that drives which `PractitionerRole` resources
exist and which `Organization` each references (see the `Practitioner` mapping above). An
`ended` affiliation stops that `PractitionerRole` from being emitted on the next sync; it is
not retroactively deleted from HAPI.

### `appointments` → `Appointment` (and `Encounter` once completed)

| Internal field | FHIR path |
|---|---|
| `id` | `Appointment.identifier` |
| `patient_id` | `Appointment.participant[?actor=Patient]` |
| `doctor_id` | `Appointment.participant[?actor=Practitioner]` |
| `scheduled_at` | `Appointment.start` |
| `status` | `Appointment.status` (`requested→proposed`, `confirmed→booked`, `completed→fulfilled`, `cancelled→cancelled`) |
| completed appointment | additionally emits an `Encounter` with `status=finished`, `period`, `reasonCode` |

### `transcripts` → `DiagnosticReport` + `Observation`s

| Internal field | FHIR path |
|---|---|
| `id` | `DiagnosticReport.identifier` |
| `recording_id` → subject | `DiagnosticReport.subject` (Patient), `DiagnosticReport.encounter` |
| `content` (transcript text) | `DiagnosticReport.presentedForm` (as `DocumentReference`) or `.conclusion` excerpt |
| `analysis.diagnosis` | `DiagnosticReport.conclusion` + `conclusionCode` |
| `analysis.symptoms[]` | one `Observation` each, `category=exam`, linked via `DiagnosticReport.result` |
| `analysis.findings[]` | `Observation` (`category=exam`) |
| `analysis.communication_quality` | `Observation` (`category=survey`) |

### imaging analysis (`images`) → `ImagingStudy` (minimal) + `DiagnosticReport`

| Internal field | FHIR path |
|---|---|
| `id` | `DiagnosticReport.identifier`, `category=RAD` |
| `storage_key` | `DocumentReference.content.attachment.url` (presigned) |
| `analysis_result` (findings / impression) | `DiagnosticReport.conclusion`, structured sections as `Observation`s |
| `modality` metadata | `ImagingStudy.series[0].modality` |

### `transcripts.medicine_recommended` → `MedicationStatement`

| Internal field | FHIR path |
|---|---|
| drug name | `MedicationStatement.medicationCodeableConcept.text` |
| dosage / frequency (if parsed) | `MedicationStatement.dosage[0]` |
| source transcript | `MedicationStatement.derivedFrom` → `DiagnosticReport` |
| `status` | `unknown` unless confirmed by a clinician → `active` |

### `documents` → `DocumentReference`

| Internal field | FHIR path |
|---|---|
| `id` | `identifier` |
| `user_id` | `subject` (Patient) |
| `storage_key` | `content.attachment.url` |
| `mime_type` | `content.attachment.contentType` |
| `created_at` | `date` |
| extraction status | `docStatus` (`preliminary` while processing, `final` when ingested) |

### `chat_history` → not synced

Conversational data stays internal. If a clinician promotes a chat conclusion, it is written
as an `Observation` or `DiagnosticReport` explicitly.

---

## Sync model

- **Direction:** internal → FHIR (one-way push) for the first milestone. HAPI is the system
  of record for FHIR clients; medita-ai's relational schema is the system of record for the
  application.
- **Trigger:** resource create/update in the application enqueues an arq `fhir_sync` job
  keyed by `(entity_type, entity_id)`.
- **Idempotency:** upsert by business identifier (`conditional update` — `PUT
  Patient?identifier=...`).
- **Failure:** recorded in `processing_status` with `entity_type='fhir_sync'`; retried with
  backoff.

Two-way sync and external FHIR ingestion are out of scope for the first milestone and tracked
as future work.

---

## Safety notes

- AI-generated content mapped to `DiagnosticReport` / `Observation` carries
  `status = preliminary` and an extension
  `https://medita.ai/fhir/StructureDefinition/ai-generated = true` until a clinician confirms
  it.
- No resource is marked `final` / `amended` without an explicit clinician action.
