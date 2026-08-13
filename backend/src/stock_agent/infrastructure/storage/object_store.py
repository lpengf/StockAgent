"""S3-compatible object storage adapter.

Works against real AWS S3, self-hosted MinIO, or any S3 API. `put_bytes`
returns the object key and SHA-256 checksum so the metadata write can happen
in the same transaction as the DB write in the caller.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import boto3
from botocore.client import Config
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from stock_agent.config import get_settings
from stock_agent.errors import ExternalServiceError
from stock_agent.logging import get_logger

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client


_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PutResult:
    key: str
    checksum: str
    bytes_written: int


class ObjectStore:
    """Thin wrapper around boto3's S3 client.

    All calls use exponential-backoff retry on transient network errors.
    """

    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    @property
    def bucket(self) -> str:
        return self._bucket

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            _log.info("object_store.create_bucket", bucket=self._bucket)
            self._client.create_bucket(Bucket=self._bucket)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.2, min=0.2, max=2.0),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def put_bytes(self, key: str, body: bytes, content_type: str, metadata: dict[str, str] | None = None) -> PutResult:
        checksum = hashlib.sha256(body).hexdigest()
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                Metadata={"checksum": checksum, **(metadata or {})},
            )
        except Exception as exc:  # pragma: no cover — network flake
            _log.warning("object_store.put_failed", key=key, error=str(exc))
            raise ExternalServiceError("对象存储写入失败", details={"key": key, "cause": str(exc)}) from exc
        _log.info("object_store.put_ok", key=key, bytes=len(body), checksum=checksum[:12])
        return PutResult(key=key, checksum=checksum, bytes_written=len(body))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.2, min=0.2, max=2.0),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def get_bytes(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            data: bytes = response["Body"].read()
            return data
        except Exception as exc:
            raise ExternalServiceError("对象存储读取失败", details={"key": key, "cause": str(exc)}) from exc


def _build_client() -> "S3Client":
    settings = get_settings()
    config = Config(signature_version="s3v4", s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"})
    kwargs: dict[str, Any] = {
        "aws_access_key_id": settings.s3_access_key_id.get_secret_value(),
        "aws_secret_access_key": settings.s3_secret_access_key.get_secret_value(),
        "region_name": settings.s3_region,
        "config": config,
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client("s3", **kwargs)


_store: ObjectStore | None = None


def get_object_store() -> ObjectStore:
    global _store
    if _store is None:
        _store = ObjectStore(_build_client(), get_settings().s3_bucket)
    return _store
