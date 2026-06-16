import os
import uuid
import logging
from contextlib import asynccontextmanager
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database import engine, Base, get_db
from config import settings
import models, r2_storage
import auth_utils
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from api.signals import _get_or_create_user_profile, _update_tag_preference, _get_video_tags
from auth_utils import (
    get_current_user,
    get_optional_current_user,
    verify_password,
    get_password_hash,
    create_access_token,
)
from api import videos as videos_api
from api import signals as signals_api
from api import feed as feed_api
from api import users as users_api
import scheduler as feed_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks — start scheduler on startup, stop on shutdown."""
    feed_scheduler.start_scheduler()
    yield
    feed_scheduler.stop_scheduler()


# Tạo bảng dữ liệu nếu chưa có
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TikTok Clone API",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers mới (modular)
app.include_router(videos_api.router)
app.include_router(signals_api.router)
app.include_router(feed_api.router)
app.include_router(users_api.router)

# Cấu hình CORS để frontend React gọi được API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,

    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đảm bảo thư mục static tồn tại để lưu file local khi cần
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(os.path.join(static_dir, "uploads"), exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Helper để tạo dữ liệu mẫu nếu DB trống
def seed_data(db: Session):
    user_count = db.query(models.User).count()
    if user_count == 0:
        print("Seeding sample data to Database...")
        # Tạo users mẫu
        user1 = models.User(
            username="alex_dance",
            hashed_password=get_password_hash("password123"), # Đơn giản hóa khi test
            display_name="Alex Dance",
            avatar_url="https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150",
            bio="Dancing is my life! Follow for daily dance covers 💃"
        )
        user2 = models.User(
            username="neon_vibes",
            hashed_password=get_password_hash("password123"),
            display_name="Neon Light Enthusiast",
            avatar_url="https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150",
            bio="Capturing the beauty of city lights at night 🌃"
        )
        db.add(user1)
        db.add(user2)
        db.commit()
        db.refresh(user1)
        db.refresh(user2)

        # Tạo videos mẫu
        video1 = models.Video(
            title="Dancing under the neon lights! #dance #vibes",
            video_url="http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
            cover_url="https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=400",
            user_id=user1.id
        )
        video2 = models.Video(
            title="Wet streets and beautiful neon signs #citylife #neon",
            video_url="http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
            cover_url="https://images.unsplash.com/photo-1514565131-fce0801e5785?w=400",
            user_id=user2.id
        )
        db.add(video1)
        db.add(video2)
        db.commit()
        db.refresh(video1)
        db.refresh(video2)

        # Tạo tương tác mẫu
        like1 = models.Like(user_id=user2.id, video_id=video1.id)
        comment1 = models.Comment(user_id=user2.id, video_id=video1.id, content="Wow, amazing moves!")
        db.add(like1)
        db.add(comment1)
        db.commit()

        # Tạo follow mẫu
        follow1 = models.Follow(follower_id=user2.id, following_id=user1.id)
        db.add(follow1)
        db.commit()

@app.on_event("startup")
def startup_event():
    """Legacy startup hook — chỉ seed data. Scheduler đã start trong lifespan."""
    db = next(get_db())
    try:
        seed_data(db)
    except Exception as e:
        logger.error(f"Error seeding data: {e}")


# Admin endpoint: trigger build feed cache manually (cho test/debug)
@app.post("/api/admin/rebuild-feeds")
def admin_rebuild_feeds(current_user: models.User = Depends(get_current_user)):
    """
    Manual trigger build feed_cache cho tất cả users.
    Yêu cầu auth (chỉ admin? hoặc open nếu dev).
    Returns summary từ build_feed_for_all_users.
    """
    from recommender import feed_cache
    summary = feed_cache.build_feed_for_all_users()
    return summary

# --- API ENDPOINTS TIÊU CHUẨN ---

@app.get("/")
def read_root():
    return {"message": "Welcome to TikTok Clone API. Go to /docs for Swagger UI API docs."}

# --- MOCK SUPABASE API ENDPOINTS ---
# Các endpoint này giúp Frontend của Toptop giao tiếp mà không cần sửa cấu trúc gọi Supabase SDK nhiều.

# 1. Auth Mockup API
@app.post("/api/auth/register")
def register(username: str = Form(...), password: str = Form(...), display_name: str = Form(...), db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pwd = get_password_hash(password)
    new_user = models.User(
        username=username,
        hashed_password=hashed_pwd,
        display_name=display_name,
        avatar_url=f"https://ui-avatars.com/api/?name={username}",
        bio="Hello, I am new here!"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {
        "id": new_user.id,
        "username": new_user.username,
        "display_name": new_user.display_name,
        "avatar_url": new_user.avatar_url
    }

@app.post("/api/auth/login")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token = create_access_token(data={"sub": str(user.id)})

    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "access_token": access_token
    }


@app.get("/api/auth/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    """
    Trả về thông tin user hiện tại (từ JWT token).
    Dùng cho FE verify session + load profile sau khi login.
    """
    return {
        "id": current_user.id,
        "username": current_user.username,
        "nickname": current_user.username,
        "display_name": current_user.display_name,
        "avatar_url": current_user.avatar_url,
        "bio": current_user.bio,
    }

# 2. Mock Supabase Storage API
@app.post("/api/storage/signed-url")
def create_signed_upload_url(payload: dict):
    file_name = payload.get("fileName")
    bucket = payload.get("bucketName", "videos")
    
    # Trả về URL PUT giả lập hướng tới backend FastAPI
    # Để đơn giản, ta trỏ tới /api/storage/upload-direct
    signed_url = f"http://localhost:8000/api/storage/upload-direct?filename={file_name}&bucket={bucket}"
    return {"signedUrl": signed_url}

@app.put("/api/storage/upload-direct")
async def upload_direct(filename: str, bucket: str, request: Request, db: Session = Depends(get_db)):
    # Đọc body stream của request (đây là file nhị phân được gửi PUT từ XMLHttpRequest ở frontend)
    body_data = await request.body()
    
    # Xác định Content-Type
    content_type = request.headers.get("content-type", "application/octet-stream")
    
    # Upload lên Cloudflare R2 (hoặc local fallback)
    public_url = r2_storage.upload_file_to_r2(body_data, filename, content_type)
    
    return {"publicUrl": public_url}

@app.post("/api/storage/public-url")
def get_storage_public_url(payload: dict):
    file_name = payload.get("fileName")
    bucket = payload.get("bucketName", "videos")
    
    # Nếu có cấu hình R2, dùng R2 Public URL
    if settings.R2_PUBLIC_URL:
        public_url = f"{settings.R2_PUBLIC_URL.rstrip('/')}/{file_name}"
    else:
        # Fallback local URL
        public_url = f"http://localhost:8000/static/uploads/{file_name}"
        
    return {"publicUrl": public_url}

# 3. Mock Supabase RPC (Remote Procedure Calls) API
@app.post("/api/rpc/{function_name}")
def execute_rpc(function_name: str, payload: dict, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(get_optional_current_user)):
    print(f"Executing Mock RPC: {function_name} with payload: {payload}")
    
    if function_name == "insert_video":
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        user_id = current_user.id

        new_video = models.Video(
            title=payload.get("description", "Video không tiêu đề"),
            video_url=payload.get("file_url"),
            cover_url=payload.get("thumb_url"),
            user_id=user_id
        )
        db.add(new_video)
        db.commit()
        return {"status": "success", "video_id": new_video.id}

    elif function_name in ["get_latest_video_by_random_users", "get_videos_feed", "get_random_videos", "get_following_videos"]:
        # Lấy feed video
        excluded_ids = payload.get("excluded_video_ids", []) or payload.get("excluded_user_ids", [])
        limit = payload.get("limit_videos", 10) or payload.get("limit", 10)
        
        query = db.query(models.Video)
        if excluded_ids:
            query = query.filter(models.Video.id.notin_(excluded_ids))
            
        videos = query.order_by(desc(models.Video.created_at)).limit(limit).all()
        
        results = []
        if not videos:
            return {"videos": results, "has_more": False}
            
        video_ids = [v.id for v in videos]
        
        # Batch counts
        likes_data = db.query(models.Like.video_id, func.count(models.Like.id)).filter(models.Like.video_id.in_(video_ids)).group_by(models.Like.video_id).all()
        likes_map = {vid: count for vid, count in likes_data}
        
        comments_data = db.query(models.Comment.video_id, func.count(models.Comment.id)).filter(models.Comment.video_id.in_(video_ids)).group_by(models.Comment.video_id).all()
        comments_map = {vid: count for vid, count in comments_data}
        
        # Batch user status
        liked_set = set()
        followed_set = set()
        if current_user:
            user_likes = db.query(models.Like.video_id).filter(models.Like.user_id == current_user.id, models.Like.video_id.in_(video_ids)).all()
            liked_set = {v[0] for v in user_likes}
            
            creator_ids = [v.user_id for v in videos]
            user_follows = db.query(models.Follow.following_id).filter(models.Follow.follower_id == current_user.id, models.Follow.following_id.in_(creator_ids)).all()
            followed_set = {v[0] for v in user_follows}

        for video in videos:
            results.append({
                "id": video.id,
                "description": video.title,
                "file_url": video.video_url,
                "thumb_url": video.cover_url or "https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=400",
                "created_at": video.created_at.isoformat() if video.created_at else None,
                "user_id": video.user_id,
                "user": {
                    "id": video.creator.id,
                    "nickname": video.creator.username,
                    "fullName": video.creator.display_name,
                    "avatar_url": video.creator.avatar_url,
                    "bio": video.creator.bio,
                    "tick": True
                },
                "user_info": {
                    "id": video.creator.id,
                    "nickname": video.creator.username,
                    "fullName": video.creator.display_name,
                    "avatar_url": video.creator.avatar_url,
                    "bio": video.creator.bio,
                    "tick": True
                },
                "likes_count": likes_map.get(video.id, 0),
                "comments_count": comments_map.get(video.id, 0),
                "shares_count": 0,
                "is_liked": video.id in liked_set,
                "is_followed": video.creator.id in followed_set
            })
        return {
            "videos": results,
            "has_more": len(results) >= limit
        }

    elif function_name == "toggle_like":
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        video_id = payload.get("video_id")
        user_id = current_user.id
        
        if not video_id:
            raise HTTPException(status_code=400, detail="Missing video_id")
            
        video = db.query(models.Video).filter(models.Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video không tồn tại")

        existing_like = db.query(models.Like).filter(
            models.Like.video_id == video_id,
            models.Like.user_id == user_id
        ).first()
        
        profile = _get_or_create_user_profile(db, user_id)
        
        if existing_like:
            db.delete(existing_like)
            video.like_count = max(0, (video.like_count or 1) - 1)
            for tag in _get_video_tags(db, video_id):
                _update_tag_preference(db, profile, tag, -0.2)
            db.commit()
            liked = False
        else:
            new_like = models.Like(user_id=user_id, video_id=video_id)
            db.add(new_like)
            video.like_count = (video.like_count or 0) + 1
            for tag in _get_video_tags(db, video_id):
                _update_tag_preference(db, profile, tag, 0.5)
            db.commit()
            liked = True
            
        return {"liked": liked, "like_count": video.like_count}

    elif function_name == "toggle_follow":
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
            
        following_id = payload.get("following_id")
        follower_id = current_user.id
        
        if not following_id:
            raise HTTPException(status_code=400, detail="Missing following_id")
            
        if following_id == follower_id:
            raise HTTPException(status_code=400, detail="Cannot follow yourself")
            
        existing_follow = db.query(models.Follow).filter(
            models.Follow.follower_id == follower_id,
            models.Follow.following_id == following_id
        ).first()
        
        if existing_follow:
            db.delete(existing_follow)
            db.commit()
            followed = False
        else:
            new_follow = models.Follow(follower_id=follower_id, following_id=following_id)
            db.add(new_follow)
            db.commit()
            followed = True
            
        return {"followed": followed}

    elif function_name == "get_following_users" or function_name == "get_follower_users":
        user_id = payload.get("user_id")
        if function_name == "get_following_users":
            follows = db.query(models.Follow).filter(models.Follow.follower_id == user_id).all()
            target_ids = [f.following_id for f in follows]
        else:
            follows = db.query(models.Follow).filter(models.Follow.following_id == user_id).all()
            target_ids = [f.follower_id for f in follows]
            
        users = db.query(models.User).filter(models.User.id.in_(target_ids)).all() if target_ids else []
        
        return [{
            "id": u.id,
            "nickname": u.username,
            "fullName": u.display_name,
            "avatar_url": u.avatar_url,
            "bio": u.bio,
            "tick": True
        } for u in users]

    elif function_name == "get_following_ids" or function_name == "get_followers_ids":
        user_id = payload.get("user_id")
        if "following" in function_name:
            follows = db.query(models.Follow).filter(models.Follow.follower_id == user_id).all()
            return [f.following_id for f in follows]
        else:
            follows = db.query(models.Follow).filter(models.Follow.following_id == user_id).all()
            return [f.follower_id for f in follows]

    elif function_name == "count_unread_messages":
        return 0

    elif function_name == "cleanup_presence_simple":
        return {"status": "ok"}

    elif function_name == "search_users":
        query_string = payload.get("query_string", "")
        limit = payload.get("limit_users", 10)
        
        users = db.query(models.User).filter(
            (models.User.username.like(f"%{query_string}%")) |
            (models.User.display_name.like(f"%{query_string}%"))
        ).limit(limit).all()
        
        return [{
            "id": u.id,
            "nickname": u.username,
            "fullName": u.display_name,
            "avatar_url": u.avatar_url,
            "tick": True
        } for u in users]
        
    return JSONResponse(status_code=400, content={"detail": f"RPC function {function_name} not implemented"})

# 4. Mock Supabase Table Querying API
@app.post("/api/table/{table_name}/query")
def query_table(table_name: str, payload: dict, db: Session = Depends(get_db)):
    # Phục vụ các lệnh như .from('user').select('*').eq('id', id)
    print(f"Table Query on: {table_name} with: {payload}")
    
    if table_name == "user":
        user_id = payload.get("id")
        email = payload.get("email")
        
        query = db.query(models.User)
        if user_id:
            query = query.filter(models.User.id == user_id)
        elif email:
            query = query.filter(models.User.username == email.split('@')[0]) # Simple mapping
            
        user = query.first()
        if not user:
            return []
            
        return [{
            "id": user.id,
            "nickname": user.username,
            "fullName": user.display_name,
            "avatar_url": user.avatar_url,
            "bio": user.bio,
            "tick": True,
            "followings_count": db.query(models.Follow).filter(models.Follow.follower_id == user.id).count(),
            "followers_count": db.query(models.Follow).filter(models.Follow.following_id == user.id).count(),
            "likes_count": db.query(models.Like).join(models.Video).filter(models.Video.user_id == user.id).count(),
        }]
        
    elif table_name == "messages":
        # Mock tin nhắn
        return []
        
    return []

@app.post("/api/table/{table_name}/insert")
def insert_table(table_name: str, payload: dict, db: Session = Depends(get_db)):
    print(f"Table Insert on: {table_name} with: {payload}")
    
    if table_name == "user":
        # Toptop đăng ký xong sẽ lưu vào bảng user
        # payload chứa: { id, email, nickname, fullName, avatar_url, ... }
        user_id = payload.get("id")
        # Do toptop gửi id dạng string (Supabase UUID), còn DB SQLite của ta là Integer.
        # Ta sẽ chuyển đổi hoặc map tạm thời
        try:
            int_id = int(user_id) if str(user_id).isdigit() else 100 + db.query(models.User).count()
        except:
            int_id = 100 + db.query(models.User).count()
            
        new_user = models.User(
            id=int_id,
            username=payload.get("nickname") or payload.get("email").split('@')[0],
            hashed_password=get_password_hash("password123"), # Default password
            display_name=payload.get("fullName"),
            avatar_url=payload.get("avatar_url"),
            bio=payload.get("bio", "")
        )
        db.add(new_user)
        db.commit()
        return {"status": "inserted"}
        
    return {"status": "ignored"}

@app.post("/api/table/{table_name}/update")
def update_table(table_name: str, payload: dict, db: Session = Depends(get_db)):
    print(f"Table Update on: {table_name} with: {payload}")
    
    if table_name == "user":
        user_id = payload.get("id")
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            if "fullName" in payload:
                user.display_name = payload["fullName"]
            if "bio" in payload:
                user.bio = payload["bio"]
            db.commit()
            return {"status": "updated"}
            
    return {"status": "ignored"}
