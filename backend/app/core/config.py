"""Application settings, read from the environment (see .env.example).

`secret_key` and `database_url` have no defaults — the app refuses to start
without them, by design (docs/architecture.md section 9).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"

    # Auth
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Qdrant
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "medita_documents"

    # MinIO / S3-compatible object storage
    minio_endpoint: str = "minio:9000"
    minio_root_user: str = "medita"
    minio_root_password: str = "medita"
    minio_use_ssl: bool = False
    minio_media_bucket: str = "medita-media"
    minio_docs_bucket: str = "medita-docs"

    # LiteLLM gateway — application code only ever references the logical
    # model names below, never a provider-specific model id.
    litellm_url: str = "http://litellm:4000"
    litellm_master_key: str = ""
    litellm_model_chat: str = "chat-default"
    litellm_model_vision: str = "vision-default"
    litellm_model_embed: str = "embed-default"

    # FHIR
    hapi_fhir_url: str = "http://hapi-fhir:8080/fhir"

    # Email (MailHog in dev — see infra's `tools` compose profile). Best-effort
    # only: services/notifications.py never lets a send failure fail a request.
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_from_address: str = "no-reply@medita.ai"
    smtp_timeout_seconds: int = 5

    # Comma-separated, e.g. "http://localhost:3000,http://localhost:8080"
    cors_origins: str = "http://localhost:3000,http://localhost:8080"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # required fields come from the environment


settings = get_settings()
