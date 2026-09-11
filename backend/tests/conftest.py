"""Pytest bootstrap: set required env vars before anything imports
app.core.config (which fails fast if SECRET_KEY / DATABASE_URL are unset)."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENV", "test")
