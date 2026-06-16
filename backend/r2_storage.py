import os
import boto3
from botocore.config import Config
from config import settings


def get_r2_client():
    # Kiểm tra xem có cấu hình R2 đầy đủ không
    if not all([settings.R2_ACCOUNT_ID, settings.R2_ACCESS_KEY_ID, settings.R2_SECRET_ACCESS_KEY, settings.R2_BUCKET_NAME]):
        return None

    endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    try:
        r2 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto"
        )
        return r2
    except Exception as e:
        print(f"Error creating R2 client: {e}")
        return None


def _save_locally(file_data: bytes, file_name: str) -> str:
    """Fallback: lưu local, return URL tương đối."""
    static_dir = os.path.join(os.path.dirname(__file__), "static", "uploads")
    os.makedirs(static_dir, exist_ok=True)
    local_path = os.path.join(static_dir, file_name)
    with open(local_path, "wb") as f:
        f.write(file_data)
    return f"http://localhost:8000/static/uploads/{file_name}"


def upload_file_to_r2(file_data: bytes, file_name: str, content_type: str) -> str:
    """Upload file lên R2 (hoặc local fallback). Return public URL."""
    r2 = get_r2_client()

    if r2 is None:
        print("R2 is not configured or error occurred. Falling back to local storage...")
        return _save_locally(file_data, file_name)

    try:
        r2.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=file_name,
            Body=file_data,
            ContentType=content_type
        )
        public_url = settings.R2_PUBLIC_URL.rstrip("/")
        return f"{public_url}/{file_name}"
    except Exception as e:
        print(f"Error uploading to R2: {e}")
        return _save_locally(file_data, file_name)


def is_r2_configured() -> bool:
    """Helper cho các endpoint muốn biết R2 có sẵn không (cho UX/dev)."""
    return get_r2_client() is not None
