"""Per-user retrieval-augmented generation over Qdrant.

One collection holds every user's document chunks; every read and write
filters by `user_id` in the point payload (docs/architecture.md, section 6). Called
from the document-ingestion job and the AI-doctor chat endpoint, both landing
in build step 5.
"""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings
from app.services.llm import embed

# Must match the output dimensionality of settings.litellm_model_embed.
_EMBEDDING_SIZE = 768


def _client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection() -> None:
    client = _client()
    if not client.collection_exists(settings.qdrant_collection):
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qmodels.VectorParams(
                size=_EMBEDDING_SIZE, distance=qmodels.Distance.COSINE
            ),
        )


def upsert_chunks(user_id: int, document_id: int, chunks: list[str]) -> None:
    if not chunks:
        return
    vectors = embed(chunks)
    points = [
        qmodels.PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={"user_id": user_id, "document_id": document_id, "text": chunk},
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    _client().upsert(collection_name=settings.qdrant_collection, points=points)


def search(user_id: int, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    [vector] = embed([query])
    results = _client().query_points(
        collection_name=settings.qdrant_collection,
        query=vector,
        query_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=user_id))]
        ),
        limit=limit,
    )
    return [
        {"text": point.payload.get("text") if point.payload else None, "score": point.score}
        for point in results.points
    ]
