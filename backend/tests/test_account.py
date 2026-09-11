"""Register -> login -> me -> refresh flow, against an isolated in-memory
SQLite database (dependency-overridden; does not touch the real engine)."""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def _override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db

client = TestClient(app)

CREDENTIALS = {
    "email": "patient@example.com",
    "password": "supersecret123",
    "full_name": "Test Patient",
}


def test_register_login_me_refresh_flow() -> None:
    register_resp = client.post("/account/register", json=CREDENTIALS)
    assert register_resp.status_code == 201
    body = register_resp.json()
    assert body["email"] == CREDENTIALS["email"]
    assert body["role"] == "patient"
    assert "hashed_password" not in body

    dup_resp = client.post("/account/register", json=CREDENTIALS)
    assert dup_resp.status_code == 409

    login_resp = client.post(
        "/account/login", json={"email": CREDENTIALS["email"], "password": CREDENTIALS["password"]}
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    assert tokens["token_type"] == "bearer"
    assert "access_token" in tokens and "refresh_token" in tokens

    bad_login_resp = client.post(
        "/account/login", json={"email": CREDENTIALS["email"], "password": "wrong-password"}
    )
    assert bad_login_resp.status_code == 401

    auth_header = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_resp = client.get("/account/me", headers=auth_header)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == CREDENTIALS["email"]

    unauthenticated_resp = client.get("/account/me")
    assert unauthenticated_resp.status_code == 401

    refresh_resp = client.post("/account/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()

    refresh_with_access_token_resp = client.post(
        "/account/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert refresh_with_access_token_resp.status_code == 401
