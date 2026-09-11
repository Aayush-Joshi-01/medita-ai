"""LLM gateway client.

Every model call goes through the LiteLLM proxy (infra/litellm/config.yaml)
via its OpenAI-compatible API. Application code references logical model
names only (settings.litellm_model_*) — never a provider-specific model id —
so changing providers is a config edit, not a code change
(docs/architecture.md, section 7).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.litellm_url,
        headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
        timeout=_TIMEOUT,
    )


def chat(messages: list[dict[str, Any]], *, model: str | None = None, **kwargs: Any) -> str:
    """Chat completion; returns the assistant's text reply."""
    with _client() as client:
        response = client.post(
            "/chat/completions",
            json={"model": model or settings.litellm_model_chat, "messages": messages, **kwargs},
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])


def vision_chat(messages: list[dict[str, Any]], *, model: str | None = None, **kwargs: Any) -> str:
    """Chat completion where message content may include image_url parts."""
    with _client() as client:
        response = client.post(
            "/chat/completions",
            json={"model": model or settings.litellm_model_vision, "messages": messages, **kwargs},
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])


def embed(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    with _client() as client:
        response = client.post(
            "/embeddings",
            json={"model": model or settings.litellm_model_embed, "input": texts},
        )
        response.raise_for_status()
        data = response.json()["data"]
        return [item["embedding"] for item in data]
