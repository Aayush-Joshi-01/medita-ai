#!/bin/sh
# One-shot bucket bootstrap, run by the `minio-init` compose service via the
# `minio/mc` image. Idempotent — safe to re-run on every `docker compose up`.
set -eu

mc alias set local "http://minio:9000" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

mc mb --ignore-existing "local/$MINIO_MEDIA_BUCKET"
mc mb --ignore-existing "local/$MINIO_DOCS_BUCKET"

echo "MinIO buckets ready: $MINIO_MEDIA_BUCKET, $MINIO_DOCS_BUCKET"
