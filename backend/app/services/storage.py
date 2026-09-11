"""Object storage service (MinIO / any S3-compatible backend).

All binary media — images, consultation recordings, uploaded documents —
lives here. Relational tables keep only the returned storage key plus
metadata; nothing binary goes into Postgres (docs/architecture.md, sections 1 and 4).
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, cast

import boto3
from botocore.client import Config as BotoConfig

from app.core.config import settings


def _client() -> Any:
    # boto3's dynamically-generated client has no first-party type stubs;
    # callers below cast the specific return values they care about.
    scheme = "https" if settings.minio_use_ssl else "http"
    return boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_root_user,
        aws_secret_access_key=settings.minio_root_password,
        config=BotoConfig(signature_version="s3v4"),
    )


def put_object(bucket: str, data: bytes, *, content_type: str, key_prefix: str = "") -> str:
    """Upload bytes under a generated key and return that key."""
    key = f"{key_prefix}{uuid.uuid4()}"
    _client().put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    return key


def get_object(bucket: str, key: str) -> bytes:
    response = _client().get_object(Bucket=bucket, Key=key)
    return cast(bytes, response["Body"].read())


def delete_object(bucket: str, key: str) -> None:
    _client().delete_object(Bucket=bucket, Key=key)


def presigned_url(bucket: str, key: str, *, expires_in: timedelta = timedelta(minutes=15)) -> str:
    return cast(
        str,
        _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=int(expires_in.total_seconds()),
        ),
    )
