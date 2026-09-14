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

### Step 3 — Backend core (2026-09-12)

Added:

- `app/core/config.py` — `Settings` (pydantic-settings) reading every variable from
  `.env.example`; `secret_key` and `database_url` have no defaults, so the app fails fast if
  either is unset.
- `app/core/security.py` — bcrypt password hashing (direct `bcrypt`, not passlib — sidesteps
  its known incompatibility warning with recent bcrypt releases) and JWT access/refresh token
  issuance + decoding (`python-jose`).
- `app/core/errors.py` — `AppError` hierarchy (`NotFoundError`, `ConflictError`, `AuthError`,
  `ForbiddenError`) and exception handlers producing a consistent
  `{"error": {"code", "message", "details"?}}` envelope, registered in `app/main.py`.
- `app/core/deps.py` — `get_db`, `get_current_user` (JWT bearer → `User`), `require_role(...)`
  factory for role-gated endpoints.
- `app/db/session.py` — SQLAlchemy 2.0 engine/session/`Base`, wired to `settings.database_url`.
- `app/models/user.py` — the `User` model (email, bcrypt hash, full name, `patient`/`doctor`
  role, active flag, timestamps); extended with domain relationships in step 4.
- `app/schemas/user.py` — `UserCreate`, `UserLogin`, `UserRead`, `TokenPair`, `RefreshRequest`.
- `app/api/routers/account.py` + `health.py` — `POST /account/register`, `POST
  /account/login`, `POST /account/refresh`, `GET /account/me`; `/health` now round-trips a
  real DB query. `app/main.py` is now a proper app factory (CORS, exception handlers, router
  includes).
- `app/services/storage.py` — MinIO/S3 client (`put_object` / `get_object` / `delete_object` /
  `presigned_url`), used once uploads land in step 4.
- `app/services/llm.py` — thin `httpx` client over the LiteLLM proxy's OpenAI-compatible API
  (`chat`, `vision_chat`, `embed`), referencing only the logical model names from config.
- `app/services/rag.py` — Qdrant per-user RAG (`ensure_collection`, `upsert_chunks`, `search`),
  filtered by a `user_id` payload field; embeds via `services/llm.py`.
- `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, and the first migration
  (`0001_create_users`) — Alembic now owns the schema; `create_all`/ad-hoc `CREATE INDEX` is
  not used anywhere.
- `tests/conftest.py`, `tests/test_account.py` — a full register → duplicate-rejects → login →
  bad-password-rejects → me → unauthenticated-rejects → refresh → refresh-with-access-token-
  rejects flow, against an isolated in-memory SQLite database via a `get_db` dependency
  override.
- `backend/pyproject.toml` — added sqlalchemy, alembic, psycopg2-binary, python-jose, bcrypt,
  boto3, qdrant-client, httpx, python-multipart, email-validator; ruff configured to treat
  FastAPI's `Depends(...)` argument defaults as intentional (not bugbear B008).
- `CORS_ORIGINS` added to `.env.example`.

Fixed:

- A bare `models/` line in `.gitignore` (meant for a future ML-model-weight cache) was
  silently matching `backend/app/models/` and had kept the entire SQLAlchemy models package
  out of every commit. Scoped `.gitignore`'s local-runtime-artifacts section to patterns that
  can't collide with source directories.

Verified (this environment has a working Python/uv toolchain, unlike Docker):

- `uv pip install -e ".[dev]"` installs cleanly.
- `pytest` — 2/2 passing.
- `ruff check .` and `ruff format --check .` — clean.
- `mypy .` (strict) — clean, after scoping `python_version` to 3.12 so it can parse numpy's
  stubs (pulled in transitively by qdrant-client; numpy is never imported directly) — the
  actual runtime stays on Python 3.11 per `backend/Dockerfile`.
- `alembic upgrade head` and `alembic downgrade base` both run cleanly against a throwaway
  SQLite database; inspected the resulting `users` table shape.

Not verified in this environment: running these same steps inside the actual Docker
containers against real Postgres/Qdrant/MinIO/LiteLLM — Docker Desktop's engine is still not
reachable here. The above gives good confidence the code is correct; a `docker compose up`
run on a machine with Docker running is still the first real integration test.

### Step 4a — HCP & Hospital onboarding: schema + roles (2026-09-14)

New step, inserted ahead of the domain feature port (now step 5) because appointments,
doctor–patient mapping, and the doctor directory all need real, verified doctor/hospital
accounts to be meaningful. Two-tier review model (confirmed with the user): `platform_admin`
reviews hospitals and independent HCPs; a per-hospital `hospital_admins` membership reviews
HCPs requesting that hospital. Hospital affiliation is optional for HCPs. This half of the
step is schema-only — additive, no application behavior changes yet; the API, service layer,
and notifications land in step 4b.

Added:

- `app/models/user.py` — added `UserRole.platform_admin` (global, manually-bootstrapped role;
  see `CONTRIBUTING.md`). Deliberately did **not** add a `hospital_admin` role value — that's
  modeled as membership in the new `hospital_admins` table instead (per-hospital, non-exclusive
  with a user's existing role, granted automatically on hospital approval).
- `app/models/enums.py` — shared `OnboardingStatus` (draft/submitted/under_review/
  changes_requested/approved/rejected/suspended), `OnboardingOwnerType` (hospital/hcp),
  `AffiliationStatus`.
- `app/models/specialization.py`, `hospital.py`, `hospital_admin.py`, `hcp_profile.py`,
  `hospital_affiliation.py`, `onboarding_document.py`, `onboarding_status_event.py` — the
  full onboarding schema: a hospital's application *is* its record (`hospitals.status`, no
  separate application table); `hcp_profiles` is 1:1 with `users` and independent of
  `User.is_active`; `hospital_affiliations` is the live many-to-many state, distinct from
  `hcp_profiles.requested_hospital_id` (onboarding *intent*, set once at submit);
  `onboarding_documents` is a polymorphic upload table (owner_type/owner_id, no DB-level FK
  on owner_id — integrity enforced in the service layer landing in 4b); `onboarding_status_events`
  is the audit trail.
- `alembic/versions/0002_add_platform_admin_role.py` — extends the existing `user_role`
  native enum. Isolated in its own migration, wrapped in `op.get_context().autocommit_block()`
  — `ALTER TYPE ... ADD VALUE` cannot share a transaction with anything using the new value,
  and Alembic wraps each migration in one transaction by default. `downgrade()` is a
  documented no-op (Postgres can't cleanly drop an enum value).
- `alembic/versions/0003_create_onboarding_schema.py` — two fresh native enums
  (`onboarding_status`, `onboarding_owner_type`) + all 7 tables above, FK-ordered. Safe as one
  migration — everything here is a brand-new `CREATE TYPE`/`CREATE TABLE`, none of 0002's
  enum-extension hazard.
- `app/schemas/specialization.py`, `hospital.py`, `hcp.py`, `onboarding.py` — response/request
  models for the API landing in 4b.
- `app/seeds/load.py` — idempotent specialization seeder (cardiology, dermatology,
  gastroenterology, neurology, general medicine); this is what `make seed` now actually runs.
- `docs/fhir-mapping.md` — added `hospitals → Organization`, fixed the doctor mapping's stale
  `specialization_id` reference to `hcp_profiles.primary_specialization_id`, and documented
  `hospital_affiliations (active) → PractitionerRole.organization` (one `PractitionerRole` per
  active affiliation).
- `docs/features.md`, `docs/architecture.md` — Hospital/HCP onboarding sections; corrected
  several stale step-number references left over from this step being inserted ahead of the
  old step 4 (now step 5).

Verified locally (same real Python/uv toolchain as step 3; Docker Desktop's engine is still
not reachable in this sandbox):

- `ruff check`/`format`, `mypy --strict` — clean across all new/changed files.
- `pytest` — all existing tests still pass; critically, `tests/test_account.py`'s
  `Base.metadata.create_all()` now builds all 7 new tables (plus `users`) against SQLite as a
  side effect of every model being registered in `app/models/__init__.py` — a real structural
  check of every column/FK/index, not just an import check. Manually inspected the generated
  `CREATE TABLE` statements for `hospitals`, `hcp_profiles`, `hospital_affiliations`, and
  `onboarding_documents` to confirm FKs and constraints match the design.
- `alembic history` confirms the revision chain resolves correctly: `0001 → 0002 → 0003 (head)`.

Not verified in this environment: actually running `alembic upgrade head` for 0002/0003 —
0002 uses Postgres-only `ALTER TYPE` syntax that has no SQLite equivalent, so the full chain
can only be exercised against real Postgres (step 2's `docker compose up` gap applies here
too). The `Base.metadata.create_all()` check above gives strong confidence the table shapes
are correct independent of that.

### Planned next steps

- Step 4b — HCP & Hospital onboarding: API + notifications (`services/onboarding.py`,
  `services/notifications.py`, `hospitals.py`/`hcp.py` routers, MailHog wiring, full test
  suite).
- Step 5 — Domain feature port (doctors directory, doctor–patient mapping, appointments,
  chat/chat-history, AI doctor personas + RAG, image analysis, transcription + analysis,
  knowledge base) with arq workers.
- Step 6 — FHIR layer (sync implementation; the mapping is already documented).
- Step 7 — Frontend implementation.
- Step 8 — Tests, CI, observability.
