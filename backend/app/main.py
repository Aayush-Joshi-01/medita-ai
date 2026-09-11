"""medita-ai backend entrypoint.

Scaffolding-stage stub: exposes a health endpoint so the container builds,
runs, and satisfies the docker-compose healthcheck. The real application
factory — routers, database, auth, error handlers — lands in build step 2
("backend core"). See docs/architecture.md for the target shape of this
module.
"""

from fastapi import FastAPI

app = FastAPI(title="medita-ai API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "medita-ai-backend"}
