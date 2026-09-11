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

### Step 2 — Monorepo + infra scaffolding (2026-09-11)

Added:

- `docker-compose.yml` — full dev stack: `proxy` (nginx), `frontend`, `backend`, `worker`,
  `db` (Postgres 16, app + FHIR databases), `redis`, `qdrant`, `minio` + `minio-init`,
  `litellm`, `hapi-fhir`, plus opt-in `tools` (`mailhog`, `adminer`) and `observability`
  (`prometheus`, `grafana`) profiles. Healthchecks and `depends_on: condition: service_healthy`
  wired where the base images support them.
- `docker-compose.prod.yml` — production overlay: builds the `prod` Dockerfile stage, strips
  dev bind-mounts and host port publishing on internal services, adds restart policies.
- `.env.example` — every variable used across compose and services, documented.
- `Makefile` — `up` / `down` / `logs` / `ps` / `build` / `tools` / `observability` targets are
  live now; `migrate` / `seed` / `test` / `lint` / `fmt` / `gen-client` are defined but wait on
  backend/frontend application code from later steps.
- `backend/` — FastAPI stub app (`app/main.py`, `GET /health`), multi-stage `Dockerfile`
  (dev/prod), `pyproject.toml` (uv-managed, ruff/mypy/pytest configured), a smoke test, and
  empty `core/ db/ models/ schemas/ api/routers/ services/ workers/ prompts/` packages with
  docstring placeholders marking which build step fills each one. `worker_stub.py` keeps the
  `worker` container alive until the real arq consumer lands in step 3.
- `frontend/` — hand-scaffolded Next.js 15 (App Router) + TypeScript + Tailwind + ESLint
  project (no network-dependent generator used), multi-stage `Dockerfile` (dev/prod,
  `output: "standalone"`), a placeholder home page, and empty `components/` / `lib/`
  directories for the real UI landing in step 6.
- `infra/` — `postgres/init/01-create-databases.sql` (FHIR database), `qdrant/config.yaml`,
  `redis/redis.conf`, `litellm/config.yaml` (provider-routed `chat-default` /
  `vision-default` / `embed-default` logical models), `minio/init-buckets.sh` (bucket
  bootstrap), `nginx/default.conf` (reverse proxy), `prometheus/prometheus.yml`,
  `grafana/provisioning/datasources/prometheus.yml`, `hapi-fhir/README.md` (documents the
  env-var-only config approach).

Verified:

- `docker compose config` and `docker compose -f docker-compose.yml -f
  docker-compose.prod.yml config` both validate cleanly.
- The prod overlay's `!reset []` correctly strips `ports`/`volumes` from `frontend`/`backend`/
  data services when resolved.

Not verified in this environment: an actual `docker compose up` run — the Docker Desktop
engine was not reachable here (CLI present, daemon not running). Run `docker compose up -d`
locally and check `docker compose ps` before relying on this stack.

### Planned next steps

- Step 3 — Backend core: FastAPI factory, config, security, database, Alembic baseline,
  storage/LLM/RAG services, auth endpoints.
- Step 4 — Domain feature port (AI doctor, imaging, transcription, RAG, doctor–patient,
  appointments, knowledge base) with arq workers.
- Step 5 — FHIR layer.
- Step 6 — Frontend implementation.
- Step 7 — Tests, CI, observability.
