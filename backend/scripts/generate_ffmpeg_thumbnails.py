"""Generate FFmpeg thumbnails cho 100 TikTok videos, update cover_url trong DB.

Dùng frame đầu tiên (0.5s) làm thumbnail.
Reliable hơn TikTok CDN URLs (có thể expire).
"""
import os
import sys
import subprocess
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models
from database import SessionLocal


def make_thumbnail(video_path: str, thumb_path: str) -> bool:
    """Extract frame làm JPG thumbnail. Thử nhiều timestamp nếu fail."""
    if os.path.exists(thumb_path):
        return True
    # Try different timestamps: 0.5s first, then 0s (first frame)
    for ss in ["00:00:00.5", "00:00:00", "00:00:01"]:
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-i", video_path,
                    "-ss", ss,
                    "-vframes", "1",
                    "-q:v", "3",
                    "-update", "1",
                    "-y",
                    thumb_path,
                ],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and os.path.exists(thumb_path):
                return True
        except Exception as e:
            continue
    return False


def main():
    db = SessionLocal()
    upload_dir = "static/uploads/videos"
    thumb_dir = "static/uploads/thumbnails"

    videos = db.query(models.Video).filter(
        models.Video.video_url.like("/static/uploads/videos/%")
    ).all()
    print(f"Found {len(videos)} TikTok videos to process")

    updated = 0
    for v in videos:
        # Build paths
        rel = v.video_url.lstrip("/")
        # video_url is /static/uploads/videos/<id>.mp4
        fname = os.path.basename(rel)
        video_path = os.path.join(upload_dir, fname)
        thumb_fname = fname.replace(".mp4", ".jpg")
        thumb_path = os.path.join(thumb_dir, thumb_fname)

        if not os.path.exists(video_path):
            print(f"  SKIP id={v.id} - video not found: {video_path}")
            continue

        if make_thumbnail(video_path, thumb_path):
            # Update cover_url in DB
            v.cover_url = f"/static/uploads/thumbnails/{thumb_fname}"
            updated += 1
            if updated % 10 == 0:
                print(f"  [{updated}] Generated thumb for id={v.id}")
        else:
            print(f"  FAIL id={v.id} - ffmpeg error")

    db.commit()
    print(f"\n✓ Updated {updated} video cover_url")

    # Sample verification
    sample = db.query(models.Video).filter(models.Video.cover_url.isnot(None)).first()
    if sample:
        print(f"  Sample: id={sample.id} cover_url={sample.cover_url}")
        # Verify file exists
        full = sample.cover_url.lstrip("/")
        print(f"  File exists: {os.path.exists(full)}")

    db.close()


if __name__ == "__main__":
    main()
