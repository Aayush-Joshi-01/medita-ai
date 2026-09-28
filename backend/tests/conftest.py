"""Pytest bootstrap + shared fixtures.

Sets required env vars before anything imports app.core.config (which fails
fast if SECRET_KEY / DATABASE_URL are unset), then provides a fresh,
isolated, SQLite-backed TestClient per test function — no real Postgres/
MinIO/SMTP under pytest.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from dataclasses import dataclass

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENV", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.specialization import Specialization
from app.models.user import User, UserRole


@dataclass
class AppClient:
    client: TestClient
    session_factory: sessionmaker[Session]

    def register(
        self,
        email: str,
        *,
        password: str = "supersecret123",
        full_name: str = "Test User",
        role: str = "patient",
    ) -> dict[str, object]:
        resp = self.client.post(
            "/account/register",
            json={"email": email, "password": password, "full_name": full_name, "role": role},
        )
        assert resp.status_code == 201, resp.text
        return dict(resp.json())

    def login(self, email: str, password: str = "supersecret123") -> dict[str, str]:
        resp = self.client.post("/account/login", json={"email": email, "password": password})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def register_and_login(
        self, email: str, *, password: str = "supersecret123", role: str = "patient"
    ) -> dict[str, str]:
        self.register(email, password=password, role=role)
        return self.login(email, password)

    def set_role(self, email: str, role: UserRole) -> None:
        """Bypass the API to set a role with no self-service grant path
        (platform_admin) — mirrors the manual bootstrap in CONTRIBUTING.md."""
        db = self.session_factory()
        try:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            user.role = role
            db.commit()
        finally:
            db.close()

    def add_specialization(self, name: str = "Cardiology") -> int:
        db = self.session_factory()
        try:
            spec = Specialization(name=name)
            db.add(spec)
            db.commit()
            db.refresh(spec)
            return spec.id
        finally:
            db.close()


@pytest.fixture()
def app_client() -> Generator[AppClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def _override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield AppClient(client=test_client, session_factory=session_factory)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def client(app_client: AppClient) -> TestClient:
    """Plain TestClient, for tests that don't need the extra helpers."""
    return app_client.client


@pytest.fixture()
def fake_storage(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    """In-memory stand-in for services/storage.py — no real MinIO under
    pytest. Patches the module services/onboarding.py calls through."""
    store: dict[str, bytes] = {}

    def fake_put_object(
        bucket: str, data: bytes, *, content_type: str, key_prefix: str = ""
    ) -> str:
        key = f"{key_prefix}{len(store)}"
        store[key] = data
        return key

    def fake_get_object(bucket: str, key: str) -> bytes:
        return store[key]

    def fake_delete_object(bucket: str, key: str) -> None:
        store.pop(key, None)

    monkeypatch.setattr("app.services.storage.put_object", fake_put_object)
    monkeypatch.setattr("app.services.storage.get_object", fake_get_object)
    monkeypatch.setattr("app.services.storage.delete_object", fake_delete_object)
    return store
