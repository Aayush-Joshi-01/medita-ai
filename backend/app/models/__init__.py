"""SQLAlchemy models. Import each model module here so it registers with
Base.metadata — required for Alembic autogenerate and for
Base.metadata.create_all() in tests.

One model per file (users, appointments, images, documents, recordings,
transcripts, chat_history, processing_status, ...); the rest land in build
step 3 ("domain feature port")."""

from app.models.user import User, UserRole  # noqa: F401
