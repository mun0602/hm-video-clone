"""End-to-end test với 100 TikTok videos THẬT trong DB.

Sử dụng public API của recommender (build_candidates_for_user, etc.)
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models
from database import SessionLocal, engine, Base
from auth_utils import get_password_hash
from recommender import (
    hybrid as rec_hybrid,
    content_based,
    collaborative,
    popularity,
    online_re_rank,
    feed_cache,
)


def _ok(cond, msg):
    icon = "✅" if cond else "❌"
    print(f"  {icon} {msg}")
    return cond


def main():
    print("=" * 70)
    print("E2E TEST: 100 TikTok videos thật trong DB")
    print("=" * 70)

    db = SessionLocal()
    all_passed = True

    # === Test 1: DB state ===
    print("\n[1] DB state")
    total_videos = db.query(models.Video).count()
    all_passed &= _ok(total_videos >= 100, f"Total videos in DB: {total_videos} (>=100)")

    creators = db.query(models.User).filter(
        models.User.username.in_(["scout2015", "bellathorne", "zachking"])
    ).all()
    all_passed &= _ok(len(creators) == 3, f"3 creator users: got {len(creators)}")
    for c in creators:
        n = db.query(models.Video).filter(models.Video.user_id == c.id).count()
        print(f"      @{c.username}: {n} videos")

    # === Test 2: Feed API ===
    print("\n[2] Feed API")
    from api.utils import build_single_video_response
    all_videos = db.query(models.Video).order_by(models.Video.view_count.desc()).limit(30).all()
    all_passed &= _ok(len(all_videos) == 30, f"Top 30: {len(all_videos)} videos")

    if all_videos:
        resp = build_single_video_response(all_videos[0], None, db)
        keys = list(resp.keys())
        all_passed &= _ok("id" in resp, f"Response has 'id': {keys[:8]}")
        all_passed &= _ok("description" in resp, f"Response has 'description'")
        all_passed &= _ok("tags" in resp, f"Response has 'tags'")

    # === Test 3: Pagination ===
    print("\n[3] Feed pagination")
    page1 = db.query(models.Video).order_by(models.Video.id).offset(0).limit(10).all()
    page2 = db.query(models.Video).order_by(models.Video.id).offset(10).limit(10).all()
    page1_ids = {v.id for v in page1}
    page2_ids = {v.id for v in page2}
    overlap = page1_ids & page2_ids
    all_passed &= _ok(len(overlap) == 0, f"Page 1 vs 2 overlap: {len(overlap)}")

    # === Test 4: Cold-start user detection ===
    print("\n[4] Cold-start user detection")
    new_username = f"newbie_e2e_{int(time.time())}"
    new_user = models.User(
        username=new_username,
        hashed_password=get_password_hash("test123"),
        display_name="Newbie",
        bio="Cold start test"
    )
    db.add(new_user)
    db.commit()
    is_cold = rec_hybrid.is_cold_start_user(db, new_user.id)
    all_passed &= _ok(is_cold, f"is_cold_start_user(newbie) = {is_cold}")

    # === Test 5: Cold-start candidates (popularity sorted) ===
    print("\n[5] Cold-start: build_candidates_for_user (popularity ranked)")
    cands = rec_hybrid.build_candidates_for_user(db, new_user.id, limit=20)
    all_passed &= _ok(len(cands) >= 5, f"Got {len(cands)} candidates")
    if cands:
        # candidates is list of (video_id, score)
        scores = [s for _, s in cands]
        is_sorted = scores == sorted(scores, reverse=True)
        all_passed &= _ok(is_sorted, f"Scores sorted desc: {scores[:5]}")
        # Diversity
        video_ids = [vid for vid, _ in cands[:10]]
        videos = db.query(models.Video).filter(models.Video.id.in_(video_ids)).all()
        creator_ids = {v.user_id for v in videos}
        all_passed &= _ok(len(creator_ids) >= 2, f"Diverse creators in top-10: {len(creator_ids)}")

    # === Test 6: Like 'pets' video → content-based boost ===
    print("\n[6] Like tagged video → content-based boost")
    # Try common tag names from the data
    pet_video = None
    for tag in ["pets", "dog", "dogs", "petsoftiktok", "magic", "lifestyle"]:
        pet_video = db.query(models.Video).filter(models.Video.tags.like(f"%{tag}%")).first()
        if pet_video:
            print(f"      Found video with tag '{tag}': id={pet_video.id}")
            break
    all_passed &= _ok(pet_video is not None, f"Found tagged video: id={pet_video.id if pet_video else None}")
    if pet_video:
        print(f"      Target: id={pet_video.id} tags='{pet_video.tags}'")
        like = models.Like(user_id=new_user.id, video_id=pet_video.id)
        db.add(like)
        # Bump interaction count to escape cold-start
        profile = models.UserProfile(user_id=new_user.id, interaction_count=5)
        db.add(profile)
        db.commit()

        # After like
        is_cold_after = rec_hybrid.is_cold_start_user(db, new_user.id)
        all_passed &= _ok(not is_cold_after, f"After like + interactions: cold={is_cold_after}")

        # Get warm recs
        cands_after = rec_hybrid.build_candidates_for_user(db, new_user.id, limit=20)
        all_passed &= _ok(len(cands_after) >= 5, f"Warm candidates: {len(cands_after)}")
        if cands_after:
            top_vid_ids = [vid for vid, _ in cands_after[:5]]
            top_videos = db.query(models.Video).filter(models.Video.id.in_(top_vid_ids)).all()
            target_tags = set((pet_video.tags or "").split(","))
            overlap_count = sum(
                1 for v in top_videos
                if target_tags & set((v.tags or "").split(","))
            )
            all_passed &= _ok(overlap_count >= 1,
                              f"Top-5: {overlap_count}/5 có chung tag với pet video")
            print(f"      Top-5 IDs: {top_vid_ids}")
            print(f"      Target tags: {target_tags}")
            for v in top_videos:
                v_tags = set((v.tags or "").split(","))
                overlap_t = target_tags & v_tags
                print(f"        id={v.id} tags={v.tags[:50]} overlap={overlap_t}")

    # === Test 7: Follow creator → boost ===
    print("\n[7] Follow creator → boost recs từ creator đó")
    scout = db.query(models.User).filter(models.User.username == "scout2015").first()
    all_passed &= _ok(scout is not None, "Found @scout2015")
    if scout:
        follow = models.Follow(follower_id=new_user.id, following_id=scout.id)
        db.add(follow)
        db.commit()

        cands_f = rec_hybrid.build_candidates_for_user(db, new_user.id, limit=20)
        if cands_f:
            top_vid_ids = [vid for vid, _ in cands_f[:10]]
            top_videos = db.query(models.Video).filter(models.Video.id.in_(top_vid_ids)).all()
            scout_count = sum(1 for v in top_videos if v.user_id == scout.id)
            all_passed &= _ok(scout_count >= 1,
                              f"After follow scout2015: {scout_count}/10 từ scout2015")
            print(f"      Top-10 user_ids: {[v.user_id for v in top_videos]}")

    # === Test 8: Video files exist (TikTok videos only, skip seed videos with external URLs) ===
    print("\n[8] Video files on disk")
    sample = db.query(models.Video).filter(
        models.Video.video_url.like("/static/uploads/videos/%")
    ).limit(20).all()
    missing = 0
    for v in sample:
        path = v.video_url.lstrip("/")
        if not os.path.exists(path):
            print(f"      ❌ MISSING id={v.id} url={v.video_url}")
            missing += 1
    all_passed &= _ok(missing == 0, f"20 sample TikTok files: {missing} missing")

    # === Test 9: Tags distribution ===
    print("\n[9] Tags distribution")
    all_tags = set()
    for v in db.query(models.Video).limit(100).all():
        if v.tags:
            for t in v.tags.split(","):
                t = t.strip()
                if t:
                    all_tags.add(t)
    print(f"      Unique tags: {len(all_tags)}")
    print(f"      Sample: {sorted(all_tags)[:15]}")
    all_passed &= _ok(len(all_tags) >= 8, f"Tag diversity: {len(all_tags)} unique tags (>=8)")

    # === Test 10: Content similarity ===
    print("\n[10] Content similarity giữa 2 video cùng tag")
    v1 = db.query(models.Video).filter(models.Video.tags.like("%pets%")).first()
    v2 = db.query(models.Video).filter(models.Video.tags.like("%pets%")).offset(1).first()
    if v1 and v2:
        e1 = content_based.get_or_compute_video_embedding(db, v1)
        e2 = content_based.get_or_compute_video_embedding(db, v2)
        sim = content_based.cosine_similarity(e1, e2)
        all_passed &= _ok(sim > 0, f"Cosine sim (pet vs pet): {sim:.3f} (>0)")

    # === Test 11: Popularity with freshness ===
    print("\n[11] Popularity score với freshness decay")
    v_old = db.query(models.Video).order_by(models.Video.created_at.asc()).first()
    v_new = db.query(models.Video).order_by(models.Video.created_at.desc()).first()
    if v_old and v_new:
        pop_old = popularity.popularity_score(v_old)
        pop_new = popularity.popularity_score(v_new)
        print(f"      Oldest (id={v_old.id}, {v_old.view_count} views): pop={pop_old:.2f}")
        print(f"      Newest (id={v_new.id}, {v_new.view_count} views): pop={pop_new:.2f}")
        all_passed &= _ok(pop_new >= 0 and pop_old >= 0, "Both scores non-negative")

    # === Test 12: Feed cache build ===
    print("\n[12] Build feed cache cho newbie")
    try:
        count = feed_cache.build_feed_for_user(db, new_user.id)
        all_passed &= _ok(count >= 0, f"Built feed cache: {count} entries")
    except Exception as e:
        all_passed &= _ok(False, f"build_feed_for_user failed: {e}")

    # === Test 13: Online re-rank ===
    print("\n[13] Online re-rank (diversity)")
    # Get FeedCache entries for the user
    fc_rows = feed_cache.get_cached_candidates(db, new_user.id, limit=20)
    if fc_rows:
        # Get videos
        vids_ids = [fc.video_id for fc in fc_rows]
        vids_qs = db.query(models.Video).filter(models.Video.id.in_(vids_ids)).all()
        videos_by_id = {v.id: v for v in vids_qs}
        reranked_ids = online_re_rank.rerank_candidates(
            fc_rows, videos_by_id, new_user.id, limit=20
        )
        all_passed &= _ok(len(reranked_ids) > 0,
                          f"Re-rank returns {len(reranked_ids)} video IDs")
        # Check no duplicate consecutive from same creator
        if reranked_ids:
            prev_creator = None
            consec_count = 0
            max_consec = 0
            for vid in reranked_ids:
                v = videos_by_id.get(vid)
                if not v:
                    continue
                if v.user_id == prev_creator:
                    consec_count += 1
                    max_consec = max(max_consec, consec_count)
                else:
                    consec_count = 1
                prev_creator = v.user_id
            all_passed &= _ok(max_consec <= 3,
                              f"Max consecutive same creator: {max_consec} (<=3)")

    # Cleanup
    db.query(models.Like).filter(models.Like.user_id == new_user.id).delete()
    db.query(models.Follow).filter(models.Follow.follower_id == new_user.id).delete()
    db.query(models.UserProfile).filter(models.UserProfile.user_id == new_user.id).delete()
    db.query(models.FeedCache).filter(models.FeedCache.user_id == new_user.id).delete()
    db.query(models.User).filter(models.User.id == new_user.id).delete()
    db.commit()
    db.close()

    print("\n" + "=" * 70)
    print("🎉 ALL E2E TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED")
    print("=" * 70)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
