"""Video processing: thumbnail generation + duration detection via FFmpeg."""
import os
import shutil
import subprocess
import tempfile
from typing import Optional, Tuple


def _which_ffmpeg() -> Optional[str]:
    """Tìm đường dẫn ffmpeg executable, hoặc None nếu chưa cài."""
    return shutil.which("ffmpeg")


def is_ffmpeg_available() -> bool:
    """Check xem FFmpeg có sẵn trên hệ thống không."""
    return _which_ffmpeg() is not None


def get_video_duration(video_path: str) -> Optional[int]:
    """
    Trả về duration của video (giây), hoặc None nếu không detect được.
    Dùng ffprobe (đi kèm FFmpeg) — nhẹ hơn parse ffmpeg output.
    """
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        return int(float(result.stdout.strip()))
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return None


def generate_thumbnail(
    video_path: str,
    output_path: Optional[str] = None,
    time_offset: float = 1.0,
    width: int = 720,
) -> Optional[str]:
    """
    Tạo thumbnail từ video ở time_offset (giây).
    Trả về path của thumbnail, hoặc None nếu fail.

    Nếu output_path=None, tạo file tạm cùng thư mục với video (.jpg).
    """
    ffmpeg = _which_ffmpeg()
    if not ffmpeg:
        return None

    if output_path is None:
        base, _ = os.path.splitext(video_path)
        output_path = f"{base}.thumb.jpg"

    try:
        # Lấy frame ở time_offset, scale về width (giữ aspect ratio)
        result = subprocess.run(
            [
                ffmpeg,
                "-y",                                # overwrite
                "-ss", str(time_offset),             # seek trước khi decode (nhanh)
                "-i", video_path,
                "-vframes", "1",                     # chỉ 1 frame
                "-vf", f"scale={width}:-1",          # scale giữ ratio
                "-q:v", "3",                         # quality (lower = better, 2-5 OK)
                output_path,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return output_path if os.path.exists(output_path) else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def process_uploaded_video(
    video_bytes: bytes,
    filename: str,
) -> Tuple[Optional[int], Optional[bytes]]:
    """
    Process video sau khi upload: trích duration + thumbnail bytes.
    Returns (duration_seconds, thumbnail_bytes).
    Nếu FFmpeg không có sẵn → return (None, None) — caller fallback về defaults.
    """
    if not is_ffmpeg_available():
        return None, None

    tmp_dir = tempfile.mkdtemp(prefix="upload_")
    try:
        # Ghi video ra file tạm (FFmpeg cần đọc từ file)
        # Filename có thể chứa "/" (vd videos/abc.mp4) → chỉ giữ basename để tránh tạo subdir
        safe_name = os.path.basename(filename) or "video.mp4"
        tmp_video = os.path.join(tmp_dir, safe_name)
        with open(tmp_video, "wb") as f:
            f.write(video_bytes)

        # Get duration
        duration = get_video_duration(tmp_video)

        # Generate thumbnail
        thumb_path = generate_thumbnail(tmp_video, time_offset=min(1.0, (duration or 1) / 2))
        thumb_bytes = None
        if thumb_path and os.path.exists(thumb_path):
            with open(thumb_path, "rb") as f:
                thumb_bytes = f.read()

        return duration, thumb_bytes
    finally:
        # Cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)
