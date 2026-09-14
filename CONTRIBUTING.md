# Contributing

## Repository model

`medita-ai` is a monorepo:

| Path | Contents |
|---|---|
| `backend/` | FastAPI service, arq workers, Alembic migrations, seeds, tests |
| `frontend/` | Next.js application |
| `infra/` | docker-compose service configuration |
| `docs/` | architecture and design documentation |

## Local setup

```bash
cp .env.example .env      # fill in secrets and LLM provider keys
docker compose up -d      # full stack
make migrate              # apply migrations
make seed                 # load demo data
make test                 # backend + frontend tests
```

Prerequisites: Docker + Docker Compose. Host installs of Python or Node are only needed for
running tooling outside containers. See [`CHANGELOG.md`](CHANGELOG.md) for exactly which
endpoints/features are live at each step.

### Bootstrapping the first platform_admin

There's no self-service way to become a `platform_admin` (the role that reviews hospital
applications and independent HCP applications) — by design, it's rare and trusted. After
registering a normal account, promote it directly in the database:

```sql
UPDATE users SET role = 'platform_admin' WHERE email = 'you@example.com';
```

Via `adminer` (`docker compose --profile tools up -d`, then `localhost:8081`) or `psql` against
the `db` service.

## Conventions

### Backend

- Python, FastAPI, SQLAlchemy 2.0. Dependency management with `uv`.
- Layering: `api/routers` (HTTP only) → `services` (business logic + external I/O) →
  `models` (persistence). Routers never call external APIs directly.
- All schema changes go through Alembic migrations. `Base.metadata.create_all` is not used.
- Lint/type: `ruff` + `mypy`. Run `make lint` before pushing.
- LLM calls go through `services/llm.py` only; never import a provider SDK elsewhere.

### Frontend

- Next.js App Router, TypeScript, Tailwind, shadcn/ui.
- Server data via TanStack Query; the API client is generated (`make gen-client`) — do not
  hand-write request code against the backend.
- Lint/type: `eslint` + `tsc --noEmit`.

### Documentation

- Update `docs/` and `CHANGELOG.md` in the same change that alters behaviour.
- Keep `docs/features.md` status fields current.

## Branching and commits

- Branch off `main`: `step/<n>-<slug>`, `feat/<slug>`, `fix/<slug>`, `docs/<slug>`.
- Each build step is committed as a coherent unit with a descriptive message.
- Commit messages: imperative subject under ~72 characters, body explaining the *why* when it
  is not obvious. No trailers.
- Do not commit secrets. `.env` is ignored; document new variables in `.env.example`.

## Security

- Report anything sensitive (leaked keys, PHI exposure) privately to the maintainers rather
  than in a public issue.
- The reference repositories contained committed API keys; those have been flagged for
  revocation and must never be reintroduced.
