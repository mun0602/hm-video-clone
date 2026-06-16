"""Remux tất cả .mp4 files sang format Chrome-friendly: H264 + AAC + faststart.

Lý do: yt-dlp tải về fragmented MP4 (fMP4) brands `isomiso2avc1mp41`
       mà Chrome's HTML5 video demuxer không play được
       (error: PipelineStatus::DEMUXER_ERROR_COULD_NOT_OPEN)

Fix: ffmpeg remux (copy codec, không re-encode) sang MP4 chuẩn
     với -movflags +faststart để moov atom ở đầu file
     (Chrome load progressive play ngay được).
"""
import os
import subprocess
import shutil
import sys
import glob

UPLOAD_DIR = "static/uploads/videos"


def inspect(filepath):
    """Return dict {size_kb, ftyp, has_moov, has_mdat} hoặc None nếu không phải MP4."""
    try:
        with open(filepath, "rb") as f:
            data = f.read(64)
        if len(data) < 8:
            return {"size_kb": 0, "ftyp": None, "valid": False}
        size = int.from_bytes(data[0:4], "big")
        btype = data[4:8].decode("ascii", errors="replace")
        if btype != "ftyp":
            return {"size_kb": len(data) // 1024, "ftyp": None, "valid": False, "btype": btype}
        ftyp = data[8:12].decode("ascii", errors="replace").strip()
        # Compatible brands (rest of ftyp box)
        compat = data[16:size].decode("ascii", errors="replace")
        # Find moov + mdat
        with open(filepath, "rb") as f:
            content = f.read()
        moov_idx = content.find(b"moov")
        mdat_idx = content.find(b"mdat")
        return {
            "size_kb": len(content) // 1024,
            "ftyp": ftyp,
            "compat": compat,
            "moov": moov_idx,
            "mdat": mdat_idx,
            "valid": True,
        }
    except Exception as e:
        return {"error": str(e), "valid": False}


def remux(src, dst):
    """Remux sang MP4 chuẩn faststart. Return True nếu OK."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", src,
                "-c", "copy",        # copy codec, không re-encode
                "-movflags", "+faststart",  # moov lên đầu file
                "-f", "mp4",
                "-y",                 # overwrite
                dst,
            ],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"    ffmpeg stderr: {result.stderr[-300:]}")
        return result.returncode == 0
    except Exception as e:
        print(f"    exception: {e}")
        return False


def re_encode(src, dst):
    """Re-encode H264 + AAC cho file không remux được (codec lạ)."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", src,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "26",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                "-pix_fmt", "yuv420p",
                "-f", "mp4",
                "-y",
                dst,
            ],
            capture_output=True, text=True, timeout=180,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"    re-encode exception: {e}")
        return False


def main():
    files = sorted(glob.glob(os.path.join(UPLOAD_DIR, "*.mp4")))
    print(f"Found {len(files)} .mp4 files")
    print("=" * 60)

    # Phase 1: Inspect - phân loại files
    good = []      # đã OK (mp42 chuẩn, faststart)
    remuxable = []  # fMP4 cần remux
    broken = []     # file lỗi (empty, audio-only MP3, M4A)
    for f in files:
        info = inspect(f)
        if not info.get("valid"):
            broken.append((f, "not MP4 or empty"))
            print(f"  ❌ BROKEN: {os.path.basename(f)} - {info.get('btype', info.get('error', 'unknown'))}")
            continue
        # Check if file is small (likely corrupt)
        if info["size_kb"] < 50:
            broken.append((f, f"too small: {info['size_kb']}KB"))
            print(f"  ❌ TOO SMALL: {os.path.basename(f)} - {info['size_kb']}KB")
            continue
        # Check if it's M4A or MP3
        if "M4A" in info.get("ftyp", "") or "M4A" in info.get("compat", ""):
            broken.append((f, "M4A audio"))
            print(f"  ❌ M4A: {os.path.basename(f)} - {info['ftyp']}/{info['compat']}")
            continue
        # fMP4 cần remux
        if "mp41" in info.get("compat", "") or info.get("ftyp") == "isom":
            remuxable.append(f)
        else:
            good.append(f)

    print(f"\nClassification: {len(good)} good, {len(remuxable)} need remux, {len(broken)} broken")
    if good[:3]:
        print(f"  Good sample: {[os.path.basename(g) for g in good[:3]]}")
    print()

    # Phase 2: Remux fMP4 files
    fixed = 0
    failed = 0
    for f in remuxable:
        tmp_path = f + ".remux.mp4"
        ok = remux(f, tmp_path)
        if ok and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 50 * 1024:
            shutil.move(tmp_path, f)
            fixed += 1
            if fixed % 10 == 0:
                print(f"  [remux] {fixed}/{len(remuxable)} done")
        else:
            failed += 1
            print(f"  ❌ REMUX FAILED: {os.path.basename(f)}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    print(f"\nRemux result: {fixed} fixed, {failed} failed")

    # Phase 3: Re-inspect to confirm
    print("\n" + "=" * 60)
    print("Re-inspection after fix:")
    mp42_count = 0
    still_mp41 = 0
    for f in files:
        info = inspect(f)
        if not info.get("valid"):
            continue
        if "mp42" in info.get("compat", ""):
            mp42_count += 1
        elif "mp41" in info.get("compat", ""):
            still_mp41 += 1
    print(f"  mp42 (good): {mp42_count}")
    print(f"  mp41 (still bad): {still_mp41}")
    print(f"  broken: {len(broken)}")

    # Save broken list for replacement
    if broken:
        with open("static/uploads/broken_videos.txt", "w") as f:
            for path, reason in broken:
                f.write(f"{os.path.basename(path)}\t{reason}\n")
        print(f"\nBroken list saved to static/uploads/broken_videos.txt")
        print(f"Broken files need to be replaced with valid TikTok URLs.")

    return 0 if failed == 0 and still_mp41 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
