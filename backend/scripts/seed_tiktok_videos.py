"""Seed 100 TikTok videos vào BE database.

- Tạo 3 fake creator users (scout2015, bellathorne, zachking) - password: "tiktok123"
- Insert 100 Video records với metadata từ yt-dlp JSON files
- Tags: extract từ #hashtags trong description, fallback category theo uploader
- view/like/repost/save counts: từ TikTok metadata
- created_at: random trong 30 ngày gần nhất
- Thumbnail: download từ TikTok CDN (URL có sẵn trong metadata)
"""
import os
import json
import re
import random
import hashlib
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import models
from database import SessionLocal, engine, Base
from auth_utils import get_password_hash  # bcrypt helper


DATA_DIR = Path("data/tiktok_videos")
META_DIR = DATA_DIR / "metadata"
UPLOAD_DIR = Path("static/uploads/videos")
THUMB_DIR = Path("static/uploads/thumbnails")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
THUMB_DIR.mkdir(parents=True, exist_ok=True)


# Map uploader -> (username, display_name, bio, tags_pool)
CREATORS = {
    "scout2015": {
        "username": "scout2015",
        "display_name": "Scout, Suki & Stella",
        "bio": "Pet squad 🐶🐕 #petsoftiktok #doglife",
        "default_tags": ["pets", "dogs", "cute", "foryoupage"],
    },
    "bellathorne": {
        "username": "bellathorne",
        "display_name": "Bella Thorne",
        "bio": "✨ Actress / creator / vibes",
        "default_tags": ["lifestyle", "vlog", "fashion", "aesthetic"],
    },
    "zachking": {
        "username": "zachking",
        "display_name": "Zach King",
        "bio": "Digital illusionist 🎩✨ #magic",
        "default_tags": ["magic", "illusion", "vfx", "creative"],
    },
}

DEFAULT_PASSWORD = "tiktok123"


def hash_password(pw: str) -> str:
    return get_password_hash(pw)


def extract_tags(description, uploader):
    """Extract #hashtags từ description, fallback về default tags của uploader."""
    tags = re.findall(r"#(\w+)", description or "")
    tags = [t.lower() for t in tags if len(t) > 2 and len(t) < 30]
    # Dedupe + limit 8 tags
    tags = list(dict.fromkeys(tags))[:8]
    if not tags:
        tags = CREATORS[uploader]["default_tags"]
    return tags


def pick_thumbnail_url(meta):
    """Pick best thumbnail URL (prefer originCover > cover > dynamicCover)."""
    thumbs = meta.get("thumbnails") or []
    if not thumbs:
        return None
    # Sort by preference (lower is better, e.g. -2 > -1)
    thumbs_sorted = sorted(thumbs, key=lambda t: t.get("preference", 0))
    return thumbs_sorted[0].get("url") if thumbs_sorted else None


def download_thumbnail(tiktok_id, url):
    """Download thumbnail, return relative path or None."""
    if not url:
        return None
    ext = "jpg"
    out_path = THUMB_DIR / f"tiktok_{tiktok_id}.{ext}"
    if out_path.exists():
        return str(out_path.relative_to("static"))
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            with open(out_path, "wb") as f:
                f.write(resp.read())
        return str(out_path.relative_to("static"))
    except Exception as e:
        print(f"  thumb fail {tiktok_id}: {e}")
        return None


def main():
    print("=" * 60)
    print("Seed 100 TikTok videos into BE")
    print("=" * 60)

    # Ensure schema
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # 1) Create 3 creator users
    user_id_map = {}
    for uname, info in CREATORS.items():
        existing = db.query(models.User).filter(models.User.username == uname).first()
        if existing:
            user_id_map[uname] = existing.id
            print(f"  user @{uname} already exists (id={existing.id})")
            continue
        u = models.User(
            username=uname,
            hashed_password=hash_password(DEFAULT_PASSWORD),
            display_name=info["display_name"],
            bio=info["bio"],
            avatar_url=None,
        )
        db.add(u)
        db.flush()
        user_id_map[uname] = u.id
        print(f"  ✓ created user @{uname} (id={u.id})")
    db.commit()

    # 2) Load metadata files
    meta_files = sorted(META_DIR.glob("*.json"))
    print(f"\nFound {len(meta_files)} metadata files")

    # 3) Insert videos
    inserted = 0
    skipped = 0
    for mf in meta_files:
        with open(mf) as f:
            meta = json.load(f)
        tiktok_id = meta.get("id")
        uploader = meta.get("uploader")
        if not tiktok_id or uploader not in user_id_map:
            print(f"  skip {mf.name}: unknown uploader {uploader}")
            skipped += 1
            continue

        # Check if file exists
        video_filename = f"{tiktok_id}.mp4"
        video_filepath = UPLOAD_DIR / video_filename
        if not video_filepath.exists():
            print(f"  skip {tiktok_id}: mp4 not found")
            skipped += 1
            continue

        # Skip if already in DB
        existing = db.query(models.Video).filter(
            models.Video.video_url.like(f"%{video_filename}")
        ).first()
        if existing:
            skipped += 1
            continue

        # Build record
        title = (meta.get("title") or "").strip()[:200] or "Untitled"
        tags = extract_tags(meta.get("description", ""), uploader)
        tags_csv = ",".join(tags)

        # Thumbnail
        thumb_url = pick_thumbnail_url(meta)
        thumb_path = download_thumbnail(tiktok_id, thumb_url)

        # Created at: distribute over last 30 days based on TikTok upload_date
        # but bias newer (so freshness signals matter for recommender)
        upload_date_str = meta.get("upload_date")  # YYYYMMDD
        try:
            if upload_date_str:
                base_date = datetime.strptime(upload_date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
            else:
                base_date = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
        except ValueError:
            base_date = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))

        # Add a bit of randomness so multiple videos don't all share same date
        jitter_hours = random.randint(0, 23)
        created_at = base_date + timedelta(hours=jitter_hours)

        v = models.Video(
            title=title,
            video_url=f"/static/uploads/videos/{video_filename}",
            cover_url=f"/{thumb_path}" if thumb_path else None,
            tags=tags_csv,
            user_id=user_id_map[uploader],
            created_at=created_at,
            view_count=int(meta.get("view_count") or 0),
            like_count=int(meta.get("like_count") or 0),
            share_count=int(meta.get("repost_count") or 0),
            duration_seconds=int(meta.get("duration") or 0),
        )
        db.add(v)
        inserted += 1

    db.commit()

    total = db.query(models.Video).count()
    print(f"\n✓ Inserted {inserted} videos (skipped {skipped})")
    print(f"  Total videos in DB: {total}")

    # Per-creator breakdown
    print("\nPer creator:")
    for uname, uid in user_id_map.items():
        n = db.query(models.Video).filter(models.Video.user_id == uid).count()
        print(f"  @{uname}: {n} videos")

    db.close()


if __name__ == "__main__":
    random.seed(42)  # reproducible
    main()
