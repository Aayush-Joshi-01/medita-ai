# Changelog

All notable changes to **medita-ai** are recorded here. The format is loosely based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The project is pre-release; no
version numbers are assigned yet, so entries are grouped by build step.

## [Unreleased]

### Step 1 — Documentation (2026-09-06)

Added:

- `README.md` — project overview, capability summary, architecture diagram, repository
  layout, quickstart outline, lineage from Impact Medical Accelerator 1 & 2.
- `docs/architecture.md` — target architecture: service topology, backend structure, data
  model, synchronous/asynchronous AI request flows, RAG design, LiteLLM gateway, FHIR layer,
  auth model, frontend structure, observability, testing/CI, and a table of deviations from
  the reference repositories.
- `docs/features.md` — every feature mapped to its target endpoints and frontend route, with
  per-feature status.
- `docs/fhir-mapping.md` — internal table ↔ FHIR R4 resource mapping, identifier strategy,
  one-way sync model, and AI-content safety rules.
- `CONTRIBUTING.md` — local setup expectations, code conventions, branching and commit rules.
- `CHANGELOG.md` — this file.
- Extended `.gitignore` for Node/Next.js, Docker, and editor artefacts.

Decisions recorded:

- LLM access via a **LiteLLM** gateway; providers configured, not coded.
- **Qdrant** as the vector store (native HNSW/ANN).
- **MinIO** for object storage; no binary blobs in Postgres.
- Fresh **Next.js** (App Router) frontend with **TanStack Query**; the v2 mocked prototype is
  not carried over.
- First milestone scope is the full feature set plus a FHIR interoperability foundation
  (embedded HAPI FHIR server).

### Planned next steps

- Step 2 — Monorepo + infra scaffolding: `docker-compose.yml`, `infra/` service configs,
  `.env.example`, `Makefile`, stub Dockerfiles; `docker compose up` reaches a healthy state.
- Step 3 — Backend core: FastAPI factory, config, security, database, Alembic baseline,
  storage/LLM/RAG services, auth endpoints.
- Step 4 — Domain feature port (AI doctor, imaging, transcription, RAG, doctor–patient,
  appointments, knowledge base) with arq workers.
- Step 5 — FHIR layer.
- Step 6 — Frontend implementation.
- Step 7 — Tests, CI, observability.
