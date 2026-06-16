# TikTok Clone BE Spec — hm-video-clone

**Ngày:** 2026-06-16
**Trạng thái:** Active
**Scope:** Backend only (FE UI do team khác làm)
**Base project:** hm-video-clone hiện tại

## Mục tiêu

Build backend cho web clone TikTok:
- Personalized video feed với hybrid recommendation (content + collaborative + popularity)
- Audio onboarding popup: mỗi lần vào web hỏi bật/tắt âm thanh (FE concern, BE chỉ serve page — không cần BE endpoint riêng)
- User upload video dần lên đến 10K
- Scale: 10K video, 1K users
- Track signals: view (watch time), like/unlike, follow creator, skip

## Approach: Two-stage hybrid recommendation (chốt C)

**Stage 1 (offline, mỗi 1-3 giờ):**
- Tính top 200 candidates per user → lưu `feed_cache` table
- Heavy model: content-based (tags matching) + collaborative (user-similarity) + popularity

**Stage 2 (online, real-time):**
- Serve từ cache → re-rank với context (time-of-day, skip-penalty gần đây, exploration)
- Return top 20 trong <100ms

**Cold-start:**
- User mới (no interactions) → popular + fresh
- Video mới (<24h) → boost freshness factor

## Tech stack (đã có sẵn + bổ sung)

| Layer | Tech | Note |
|---|---|---|
| Web framework | FastAPI | đã có |
| DB | PostgreSQL (prod) / SQLite (dev) | đã có |
| ORM | SQLAlchemy | đã có |
| Auth | FastAPI JWT (HS256) | đã có, sẽ cải tiến |
| Storage | Cloudflare R2 (with local fallback) | đã có |
| Recommendation | Pure Python (no ML lib) — TF-IDF cho content-based, cosine sim cho collaborative | đơn giản, đủ cho scale 10K |
| Scheduler | APScheduler (in-process) | mới, thêm |
| Video processing | FFmpeg subprocess cho thumbnail | mới, thêm |

**Lý do không dùng ML framework:** Scale 10K + 1K users quá nhỏ cho ML pipeline. Pure Python thuần đủ nhanh, dễ debug, không cần GPU.

## BE Architecture

```
backend/
├── main.py                # FastAPI app + endpoints
├── config.py              # Settings
├── database.py            # DB engine, session
├── models.py              # SQLAlchemy models
├── r2_storage.py          # Cloudflare R2 client
├── auth_utils.py          # JWT + password hashing
├── recommender/
│   ├── __init__.py
│   ├── content_based.py   # TF-IDF + cosine trên tags
│   ├── collaborative.py   # User-user cosine sim
│   ├── popularity.py      # Score theo view/like count + freshness
│   ├── hybrid.py          # Kết hợp 3 signals, ra final score
│   └── feed_cache.py      # Build/cache strategy
├── scheduler.py           # APScheduler jobs
├── video_processing.py    # FFmpeg thumbnail gen
└── tests/
    ├── test_auth.py
    ├── test_signals.py
    ├── test_recommender.py
    └── test_feed_api.py
```

## Endpoints (BE cung cấp cho FE)

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| POST | /api/auth/register | - | Đăng ký (đã có, giữ) |
| POST | /api/auth/login | - | Đăng nhập (đã có, giữ) |
| POST | /api/videos/upload | ✓ | Upload video (multipart) |
| GET | /api/videos/{id} | - | Chi tiết video |
| GET | /api/feed | ✓ | **Personalized feed** (re-ranked) |
| GET | /api/feed/explore | - | Cold-start: popular + fresh |
| POST | /api/signals/view | ✓ | Track watch_duration + is_skipped |
| POST | /api/signals/like | ✓ | Toggle like (đã có) |
| POST | /api/signals/follow | ✓ | Toggle follow (đã có) |
| GET | /api/users/{id} | - | User profile |
| GET | /api/users/{id}/videos | - | Videos của creator |

## DB Schema bổ sung

**`feed_cache`** (offline-computed candidates):
- id, user_id, video_id, score, rank, computed_at, expires_at
- Index: (user_id, rank), (expires_at)

**`video_embeddings`** (cached TF-IDF vectors):
- video_id, embedding (JSON or pickled bytes)
- Computed lazily, refreshed khi video mới

**`user_profiles`** (aggregated user signals):
- user_id, tag_preferences (JSON map tag→weight), last_active
- Updated incrementally khi có signal mới

## Implementation Tasks

| # | Task | Est. time |
|---|---|---|
| A | Enhanced JWT auth + tests | 30 min |
| B | DB schema bổ sung (feed_cache, video_embeddings, user_profiles) | 30 min |
| C | Video upload pipeline với FFmpeg thumbnail | 45 min |
| D | Signal tracking endpoints (view, like, follow) | 30 min |
| E | Recommendation engine (content + collaborative + popularity + hybrid) | 1.5h |
| F | Feed API với online re-rank | 30 min |
| G | APScheduler cho offline cache refresh | 30 min |
| H | Tests cho core flows | 1h |

## Acceptance criteria

- [ ] Auth: register, login, protected routes work với JWT
- [ ] Upload: video file lên R2 (hoặc local), thumbnail auto-gen, metadata lưu DB
- [ ] Signals: view/like/follow endpoints persist data + update user_profiles
- [ ] Recommender: cold-start (popular) + warm (hybrid) đều return valid videos
- [ ] Feed API: response <200ms, top 20 videos, có `is_liked`/`is_followed` flags
- [ ] Scheduler: feed_cache refresh mỗi 2h, log rõ ràng
- [ ] Tests: ≥80% coverage trên auth, signals, recommender

## Non-goals (làm sau nếu cần)

- Real-time messaging (đã có mock, không focus)
- Comments
- Shares
- Hashtag trending
- Creator analytics dashboard
- Admin panel

## Risks

- **FFmpeg not installed**: cần Mun ca cài `ffmpeg` trên máy. Nếu không có → fallback dùng cover_url từ FE
- **APScheduler in-process**: nếu restart service, mất scheduled jobs. Acceptable cho scale này
- **Pure Python recommendation**: nếu user count > 10K hoặc video > 100K cần ML. Đủ cho 10K+1K
