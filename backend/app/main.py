"""medita-ai backend entrypoint: FastAPI app factory.

CORS, error handling, and the account/health routers landed in step 3
("backend core"); hospitals/hcp onboarding routers in step 4. Domain routers
(chat, image, ai_doctor, doctors, appointments, transcription,
knowledge_base) land in step 5, fhir in step 6 — see docs/architecture.md
for the target shape of this module.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import account, hcp, health, hospitals
from app.core.config import settings
from app.core.errors import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="medita-ai API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(account.router)
    app.include_router(hospitals.router)
    app.include_router(hcp.router)

    return app


app = create_app()
