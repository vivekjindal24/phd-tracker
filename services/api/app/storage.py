"""S3-compatible object storage (R2 in dev, MinIO on the NAS in production). The API never
proxies file bytes: browsers PUT/GET directly with short-lived presigned URLs, issued only
after the owner record's get_or_403 (SECURITY.md §6)."""

import asyncio
import re
from functools import lru_cache

import boto3
import botocore.exceptions
from botocore.config import Config

from app.config import settings

PRESIGN_SECONDS = 300


@lru_cache(maxsize=1)
def _client():
    s3 = settings.s3
    return boto3.client(
        "s3",
        endpoint_url=s3.endpoint,
        region_name=s3.region,
        aws_access_key_id=s3.access_key_id,
        aws_secret_access_key=s3.secret_access_key,
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def safe_filename(name: str) -> str:
    """Keep names readable but header- and path-safe."""
    cleaned = re.sub(r"[^\w.\- ]", "_", name).strip(" .")
    return cleaned[:150] or "file"


def presign_put(key: str, content_type: str, size_bytes: int) -> str:
    # Content type and length are signed: the browser must upload exactly what was declared.
    return _client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.s3.bucket,
            "Key": key,
            "ContentType": content_type,
            "ContentLength": size_bytes,
        },
        ExpiresIn=PRESIGN_SECONDS,
    )


def presign_get(key: str, file_name: str) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.s3.bucket,
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{safe_filename(file_name)}"',
        },
        ExpiresIn=PRESIGN_SECONDS,
    )


async def head(key: str) -> dict | None:
    """Object metadata, or None if it does not exist. Network I/O runs off the event loop."""

    def _head() -> dict | None:
        try:
            return _client().head_object(Bucket=settings.s3.bucket, Key=key)
        except botocore.exceptions.ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    return await asyncio.to_thread(_head)


async def delete(key: str) -> None:
    """Test cleanup only — production soft-deletes the row and keeps the object."""
    await asyncio.to_thread(_client().delete_object, Bucket=settings.s3.bucket, Key=key)
