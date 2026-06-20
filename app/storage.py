from io import BytesIO
from uuid import uuid4

from minio import Minio

from app.config import Settings, get_settings


def get_minio_client(settings: Settings | None = None) -> Minio:
    settings = settings or get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket(client: Minio, bucket_name: str) -> None:
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)


async def upload_template_file(
    content: bytes,
    filename: str,
    content_type: str,
    client_id: str,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    client = get_minio_client(settings)
    ensure_bucket(client, settings.minio_bucket)

    extension = ""
    if "." in filename:
        extension = "." + filename.rsplit(".", 1)[1]

    object_name = f"{client_id}/{uuid4().hex}{extension}"

    client.put_object(
        settings.minio_bucket,
        object_name,
        BytesIO(content),
        length=len(content),
        content_type=content_type,
    )

    return object_name


def download_template_file(
    bucket: str,
    file_key: str,
    settings: Settings | None = None,
) -> bytes:
    settings = settings or get_settings()
    client = get_minio_client(settings)
    response = client.get_object(bucket, file_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def upload_preview_image(
    content: bytes,
    client_id: str,
    template_id: int,
    page_index: int,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    client = get_minio_client(settings)
    ensure_bucket(client, settings.minio_bucket)

    object_name = f"{settings.preview_key_prefix}/{client_id}/{template_id}/page_{page_index}.png"
    client.put_object(
        settings.minio_bucket,
        object_name,
        BytesIO(content),
        length=len(content),
        content_type="image/png",
    )
    return object_name


def download_preview_image(
    file_key: str,
    settings: Settings | None = None,
) -> bytes:
    settings = settings or get_settings()
    client = get_minio_client(settings)
    response = client.get_object(settings.minio_bucket, file_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
