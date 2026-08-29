"""Almacenamiento de objetos: S3/MinIO o filesystem local (FASE 7).

El backend se selecciona con la variable STORAGE_BACKEND (s3 | filesystem).
Los archivos originales jamas se modifican: se guardan bajo la clave
documents/{sha256}.pdf y se recuperan solo por descarga.
"""

from pathlib import Path

import boto3
from botocore.client import Config as BotoConfig

from app.core.config import settings


class StorageError(Exception):
    pass


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=f"http://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name="us-east-1",
        config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 2}),
    )


def ensure_bucket() -> None:
    if settings.storage_backend == "filesystem":
        Path(settings.local_storage_path).mkdir(parents=True, exist_ok=True)
        return
    client = _s3_client()
    try:
        client.head_bucket(Bucket=settings.minio_bucket)
    except Exception:
        client.create_bucket(Bucket=settings.minio_bucket)


def _filesystem_path(key: str) -> Path:
    return Path(settings.local_storage_path) / key


def upload_object(key: str, data: bytes, content_type: str = "application/pdf") -> str:
    """Guarda un objeto y devuelve su clave de almacenamiento."""
    if settings.storage_backend == "filesystem":
        path = _filesystem_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key
    client = _s3_client()
    client.put_object(Bucket=settings.minio_bucket, Key=key, Body=data, ContentType=content_type)
    return key


def upload_original(sha256: str, data: bytes, content_type: str = "application/pdf") -> str:
    """Guarda el archivo original (nunca se modifica) bajo documents/{sha256}.pdf."""
    return upload_object(f"documents/{sha256}.pdf", data, content_type)


def upload_searchable(sha256: str, data: bytes) -> str:
    """Guarda el PDF buscable generado por OCR bajo ocr/{sha256}.pdf."""
    return upload_object(f"ocr/{sha256}.pdf", data, "application/pdf")


def download_original(key: str) -> bytes:
    """Devuelve el contenido del archivo original guardado (nunca modificado)."""
    if settings.storage_backend == "filesystem":
        path = _filesystem_path(key)
        if not path.exists():
            raise StorageError("Archivo no encontrado en almacenamiento")
        return path.read_bytes()
    client = _s3_client()
    try:
        obj = client.get_object(Bucket=settings.minio_bucket, Key=key)
        return obj["Body"].read()
    except Exception as exc:
        raise StorageError("Archivo no encontrado en almacenamiento") from exc


def delete_original(key: str) -> None:
    if settings.storage_backend == "filesystem":
        _filesystem_path(key).unlink(missing_ok=True)
        return
    client = _s3_client()
    client.delete_object(Bucket=settings.minio_bucket, Key=key)


def delete_object(key: str) -> None:
    delete_original(key)


def object_exists(key: str) -> bool:
    if settings.storage_backend == "filesystem":
        return _filesystem_path(key).exists()
    client = _s3_client()
    try:
        client.head_object(Bucket=settings.minio_bucket, Key=key)
        return True
    except Exception:
        return False