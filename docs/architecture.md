# Architecture

This document describes the target architecture of **medita-ai**. It is the reference the
implementation steps build toward; sections are updated as components land.

---

## 1. Goals and constraints

- **One command to run everything.** `docker compose up` brings the full stack up healthy —
  no external managed services required for local development.
- **Provider-agnostic AI.** No SDK for a specific LLM vendor in application code; all model
  calls go through a gateway that is reconfigured, not rewritten, to change providers.
- **No binary blobs in the database.** Images, video and documents live in object storage;
  relational rows hold a storage key plus metadata.
- **Migrations, not `create_all`.** Schema is versioned with Alembic.
- **Async by default for AI work.** Long operations (image analysis, transcription,
  transcript analysis, document ingestion) run in a worker and are tracked as jobs.
- **Interoperability.** Clinical data is expressible as FHIR R4 and served from an embedded
  FHIR server.
- **Secrets are never committed.** Everything sensitive comes from the environment.

---

## 2. Service topology

| Service | Technology | Responsibility |
|---|---|---|
| `proxy` | nginx | Single ingress on `:8080`; routes `/` → frontend, `/api` → backend, `/fhir` → HAPI. |
| `frontend` | Next.js (App Router) | Web client. Server components for reads, TanStack Query for client data, generated typed API client. |
| `backend` | FastAPI + Uvicorn/Gunicorn | REST API, auth, orchestration of services. |
| `worker` | arq | Executes queued AI jobs; same image as `backend`. |
| `db` | PostgreSQL 16 | Application database and a separate FHIR database. `pgvector` available as a fallback. |
| `qdrant` | Qdrant | Vector store for per-user RAG (HNSW index, payload filtering). |
| `litellm` | LiteLLM proxy | Gateway for chat, vision and embedding calls. Holds provider keys, routing, retries, budgets. |
| `minio` | MinIO | S3-compatible object storage. Buckets: `medita-media`, `medita-docs`. |
| `redis` | Redis 7 | Job queue and cache. |
| `hapi-fhir` | HAPI FHIR JPA | FHIR R4 server, persisted in the FHIR database. |
| `mailhog` | MailHog | Captures outbound email in development. |
| `adminer` | Adminer | Database inspection (dev only). |
| `prometheus`, `grafana` | — | Metrics and dashboards (opt-in profile). |

Compose profiles: **default** (core services), **observability** (prometheus + grafana),
**tools** (adminer + mailhog). Every long-running service defines a healthcheck; `backend`
and `worker` start only after their dependencies are healthy.

---

## 3. Backend structure

```
backend/app/
├── main.py            FastAPI factory: lifespan, router include, CORS, error handlers
├── core/              config (pydantic-settings), security (JWT), logging, errors, shared deps
├── db/                engine, SessionLocal, Base, get_db
├── models/            one SQLAlchemy 2.0 model per file
├── schemas/           Pydantic v2 request/response models
├── api/routers/       account, chat, image, doctors, ai_doctor, specialization,
│                      appointments, transcription, knowledge_base, fhir, health
├── services/
│   ├── llm.py         LiteLLM client wrapper (chat / vision / embeddings)
│   ├── rag.py         Qdrant ingest + search, per-user filtering
│   ├── transcription.py  provider-abstracted STT (local whisper / groq / deepgram)
│   ├── storage.py     S3/MinIO put / get / presign
│   ├── documents.py   PDF → text chunks
│   ├── audio.py       ffmpeg extract / duration / split
│   └── fhir.py        internal model ↔ FHIR resource mapping, HAPI client
├── workers/           arq task definitions
└── prompts/           doctors_config/*.yaml specialist personas
```

**Layering rule:** routers do HTTP + validation only; services hold business logic and all
external I/O; models are persistence. Routers never call external APIs directly.

**Error handling:** a central exception handler converts a typed `AppError` hierarchy and
Pydantic validation errors into consistent JSON envelopes. Tracebacks are exposed only when
`ENV=development`.

---

## 4. Data model (application database)

Ported and cleaned from Impact Medical Accelerator 2. Legacy SQLite and the legacy
`chat_messages` table are dropped.

| Table | Purpose |
|---|---|
| `users` | Patients and doctors. Role, bcrypt hash, optional `consulting_doctor_id`, `specialization_id`. |
| `specializations` | Medical specialties. |
| `doctor_patient_mapping` | Which patients a doctor manages. |
| `appointments` | Scheduled consultations, status lifecycle. |
| `chat_history` | All chat turns (`sender_type`, `chat_context`, `read_at`). |
| `images` | Uploaded medical images: `storage_key`, `analysis_result`, JSON metadata. |
| `documents` | Uploaded records: `storage_key`, extraction status, vector reference. |
| `recordings` | Consultation media: `storage_key`, duration. |
| `transcripts` | Transcription text + structured analysis + `medicine_recommended`. |
| `user_knowledge` | Cumulative / delta patient-knowledge summary feeding RAG. |
| `processing_status` | Generic async-job tracker: `entity_type`, `entity_id`, `status`, `error`, timestamps. |
| `knowledge_articles` | Shared knowledge-base content. |

Schema is created and evolved exclusively through Alembic migrations under
`backend/alembic/versions/`.

---

## 5. AI request flow

### Synchronous (chat)

```
client → POST /api/ai-doctor/chat
       → router validates, loads persona + optional RAG context (services/rag.py → Qdrant)
       → services/llm.py → LiteLLM → provider
       → response persisted to chat_history, returned to client
```

### Asynchronous (image / transcription / ingestion)

```
client → POST /api/image  (multipart)
       → services/storage.py uploads to MinIO, row created, processing_status = pending
       → arq job enqueued, job id returned (202)
worker → picks up job, status = processing
       → services/llm.py (vision) or services/transcription.py
       → result persisted, status = completed (or failed with error)
client → GET /api/image/{id}  polls status, then reads result
```

The frontend polls status endpoints; server-sent events may be added later.

---

## 6. Retrieval-augmented generation

- Documents are parsed to markdown, chunked, and embedded via LiteLLM.
- Vectors are stored in a single Qdrant collection with a `user_id` payload field; retrieval
  always filters by the requesting user. (A collection-per-user layout is the fallback if
  payload filtering proves insufficient.)
- `user_knowledge` holds a rolling natural-language summary of a patient, refreshed as new
  documents arrive, and is prepended to specialist prompts.

---

## 7. LLM gateway (LiteLLM)

- Config lives in `infra/litellm/config.yaml`: a model list mapping logical names
  (`chat-default`, `vision-default`, `embed-default`) to concrete provider models, plus
  routing, fallbacks and per-key budgets.
- Provider API keys are passed to the `litellm` container as environment variables only.
- Application code references logical model names, never provider model IDs.

---

## 8. FHIR layer

- `hapi-fhir` runs a standard HAPI JPA server against the FHIR database.
- `services/fhir.py` maps internal records to FHIR R4 resources (see
  [`fhir-mapping.md`](fhir-mapping.md)) and pushes/reads them through the HAPI REST API.
- The `/api/fhir` router exposes read and sync operations; `/fhir` proxies directly to HAPI
  for standard client access.

---

## 9. Authentication and authorization

- JWT (HS256) access tokens + refresh tokens. `SECRET_KEY` is a required environment
  variable — the app refuses to start without it.
- Passwords hashed with bcrypt.
- Role checks (`patient`, `doctor`) are centralised in `core/deps.py` dependencies.
- Rate limiting on auth and AI endpoints.
- All AI endpoints require authentication (the v2 gap where `/transcribe` and `/analyze` were
  open is closed).

---

## 10. Frontend structure

```
frontend/src/
├── app/
│   ├── (auth)/login
│   └── (dashboard)/{dashboard,ai-doctor,chat,imaging,video-call,knowledge-base,profile}
├── components/{ui,layout}
└── lib/
    ├── api/     generated OpenAPI client (openapi-typescript + openapi-fetch)
    ├── query/   TanStack Query client, query keys, per-resource hooks
    └── auth/    token storage, session provider, route guards
```

- Server components fetch initial data; TanStack Query owns client-side cache, mutations and
  polling.
- The API client is regenerated from the backend's OpenAPI schema (`make gen-client`);
  a drift check runs in CI.
- Uploads go directly to MinIO via presigned URLs issued by the backend.

---

## 11. Observability

- Structured JSON logs from backend and worker.
- Prometheus metrics endpoint on the backend; Grafana dashboards under the `observability`
  compose profile.
- `processing_status` doubles as an audit trail for every AI operation.

---

## 12. Testing and CI

- **Backend:** pytest with `httpx.AsyncClient` against ephemeral compose services.
- **Frontend:** vitest for units, Playwright for a smoke path (login → chat → upload).
- **CI (GitHub Actions):** lint (ruff, mypy, eslint, tsc) → test → build both images →
  OpenAPI client drift check.

---

## 13. Deviations from the reference repositories

| Reference behaviour | medita-ai |
|---|---|
| `Base.metadata.create_all` + ad-hoc `CREATE INDEX` strings | Alembic migrations |
| Media stored as Postgres `LargeBinary` | MinIO object storage + storage keys |
| Dual Postgres + SQLite persistence, legacy `chat_messages` | Single Postgres, `chat_history` only |
| Committed provider API keys | Environment only; keys flagged for revocation |
| Two competing `LLM` classes, inconsistent key env vars | One `services/llm.py` over LiteLLM |
| Hosted Pinecone + dead FAISS code | Self-hosted Qdrant |
| Synchronous inline AI calls | arq workers + `processing_status` |
| Frontend fully mocked | Real generated client wired to the backend |
| `/transcribe`, `/analyze` unauthenticated | All AI endpoints authenticated |
| No Docker / tests / CI | Full compose stack, pytest + Playwright, GitHub Actions |
