# medita-ai

An AI-assisted telemedicine and clinical-support platform connecting patients and doctors.
It is the third iteration of a project previously prototyped as **Impact Medical Accelerator**
(v1, Streamlit monolith) and **Impact Medical Accelerator 2** (v2, FastAPI + mocked Next.js).
`medita-ai` re-platforms both into a production-shaped, fully containerised monorepo.

> **Medical disclaimer.** medita-ai produces AI-generated information to support clinicians
> and patients. It is not a medical device and does not provide a diagnosis. All output must
> be reviewed by a qualified professional before any clinical decision.

---

## What it does

| Capability | Description |
|---|---|
| **AI doctor chat** | Specialty-specific assistant personas (cardiology, dermatology, gastroenterology, neurology, general medicine) backed by an LLM, optionally grounded in the patient's own uploaded records (RAG). |
| **Medical imaging analysis** | Upload radiology images; generate a structured report (findings / impression) and ask follow-up questions about the image. |
| **Consultation transcription & analysis** | Upload a consultation recording; transcribe (local Whisper / Groq / Deepgram) and extract a structured summary — symptoms, findings, diagnosis, plan, medications, communication quality. |
| **Personal record RAG** | Patients upload documents; text is chunked, embedded and stored per-user in a vector database so the assistant can cite their history. |
| **Doctor–patient management** | Roles, doctor↔patient mapping, direct chat, appointment scheduling, shared knowledge base. |
| **FHIR interoperability** | Internal records are mapped to FHIR R4 resources and exposed through an embedded HAPI FHIR server for EHR interop. |

See [`docs/features.md`](docs/features.md) for the feature → endpoint → UI map.

---

## Architecture at a glance

```
                    ┌───────────── nginx reverse proxy (:8080) ─────────────┐
                    │            /            /api            /fhir          │
                    ▼            ▼             ▼               ▼
              Next.js frontend  FastAPI backend  ◄──►  HAPI FHIR server
                                    │
        ┌───────────────┬───────────┼───────────────┬───────────────┐
        ▼               ▼           ▼               ▼               ▼
   PostgreSQL        Qdrant      LiteLLM        MinIO (S3)        Redis
   (app + fhir)   (vector RAG)  (LLM gateway)  (media/docs)   (jobs + cache)
                                    ▲
                                    │
                               arq worker  (async AI jobs)
```

- **Backend** — FastAPI, SQLAlchemy 2.0, Alembic migrations, layered `api → services → models`.
- **Frontend** — Next.js (App Router), TanStack Query, shadcn/ui + Tailwind, generated OpenAPI client.
- **LLM access** — everything goes through a **LiteLLM** gateway; providers are swapped in config.
- **Vector store** — **Qdrant** (native HNSW/ANN).
- **Object storage** — **MinIO** (S3-compatible); binary media is never stored in Postgres.
- **Async jobs** — **arq** workers over Redis, tracked in a `processing_status` table.

Full detail in [`docs/architecture.md`](docs/architecture.md).

---

## Repository layout

```
medita-ai/
├── backend/     FastAPI service, workers, migrations, seeds, tests
├── frontend/    Next.js application
├── infra/       docker-compose service configs (postgres, qdrant, litellm, minio, hapi-fhir, proxy, …)
├── docs/        architecture, features, FHIR mapping
├── docker-compose.yml
├── .env.example
└── Makefile
```

---

## Quickstart

```bash
cp .env.example .env          # fill in a SECRET_KEY and any LLM provider keys you have
docker compose up -d          # bring up the full stack
docker compose ps             # confirm every service is healthy
# open http://localhost:8080
```

The monorepo and infra scaffolding is in place: every service in
[`docker-compose.yml`](docker-compose.yml) builds and starts, `backend` and `frontend` are
minimal stub apps behind the `proxy` reverse proxy, and `GET /api/health` responds. Domain
logic (auth, AI features, migrations, seed data) lands in the next build steps — `make
migrate`, `make seed` and `make test` are defined but not yet functional (see
[`CHANGELOG.md`](CHANGELOG.md) for current progress).

Optional profiles:

```bash
docker compose --profile tools up -d          # mailhog (:8025), adminer (:8081)
docker compose --profile observability up -d  # prometheus (:9090), grafana (:3001)
```

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Services, data flow, technology decisions, security model |
| [`docs/features.md`](docs/features.md) | Every feature mapped to endpoints and UI routes |
| [`docs/fhir-mapping.md`](docs/fhir-mapping.md) | Internal model ↔ FHIR R4 resource mapping |
| [`CHANGELOG.md`](CHANGELOG.md) | Chronological record of what has been built |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Local setup, conventions, commit and branching rules |

---

## Status

Early construction. The build order is: **(1) documentation ✅ → (2) monorepo + infra
scaffolding ✅ → (3) backend core → (4) domain features → (5) FHIR layer → (6) frontend → (7)
tests / CI / observability.** Each step is committed separately.

---

## Lineage

| Iteration | Form | Notes |
|---|---|---|
| Impact Medical Accelerator | Streamlit + single-file FastAPI | Original hackathon prototype. |
| Impact Medical Accelerator 2 | Modular FastAPI + mocked Next.js | Re-platform; frontend never wired to backend. |
| **medita-ai** | Containerised monorepo | This repository. Real services, migrations, tests, CI, FHIR. |
