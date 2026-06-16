from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Float, Index, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    videos = relationship("Video", back_populates="creator")
    likes = relationship("Like", back_populates="user")
    comments = relationship("Comment", back_populates="user")

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    video_url = Column(String, nullable=False)
    cover_url = Column(String, nullable=True)
    tags = Column(String, nullable=True) # Store comma-separated tags
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    # Engagement counters (denormalized cho fast recommendation)
    view_count = Column(Integer, default=0, index=True)
    like_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    duration_seconds = Column(Integer, nullable=True)  # filled bởi FFmpeg

    creator = relationship("User", back_populates="videos")
    likes = relationship("Like", back_populates="video", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="video", cascade="all, delete-orphan")
    views = relationship("VideoView", back_populates="video", cascade="all, delete-orphan")

class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="likes")
    video = relationship("Video", back_populates="likes")

    __table_args__ = (
        Index("ix_likes_user_video", "user_id", "video_id", unique=True),
    )

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="comments")
    video = relationship("Video", back_populates="comments")

class Follow(Base):
    __tablename__ = "follows"

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    following_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_follows_pair", "follower_id", "following_id", unique=True),
    )

class VideoView(Base):
    __tablename__ = "video_views"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    watch_duration = Column(Integer, default=0)  # Duration in seconds
    is_skipped = Column(Integer, default=0)       # 1 if skipped (swipe away trong <2s)
    is_rewatched = Column(Integer, default=0)     # 1 if rewatched
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    video = relationship("Video", back_populates="views")


# ============================================================
# Recommendation-related tables
# ============================================================

class FeedCache(Base):
    """
    Pre-computed candidates per user (offline job, refresh mỗi 1-3h).
    Online re-rank sẽ query bảng này thay vì score lại toàn bộ 10K videos.
    """
    __tablename__ = "feed_cache"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    score = Column(Float, default=0.0)       # raw hybrid score từ offline job
    rank = Column(Integer, default=0)        # 0..199 (top 200)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (
        Index("ix_feed_user_rank", "user_id", "rank"),
        Index("ix_feed_user_video", "user_id", "video_id", unique=True),
    )


class VideoEmbedding(Base):
    """
    Cache TF-IDF vector cho content-based recommendation.
    Vector lưu dạng bytes (pickled numpy hoặc list of floats).
    Computed lazily khi video mới hoặc tags đổi.
    """
    __tablename__ = "video_embeddings"

    video_id = Column(Integer, ForeignKey("videos.id"), primary_key=True)
    embedding = Column(LargeBinary, nullable=False)  # pickled dict {tag: tfidf_weight}
    tag_hash = Column(String, nullable=False)         # hash of tags string — invalidate khi tags đổi
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class UserProfile(Base):
    """
    Aggregated user signals (cho collaborative + content boost).
    Updated incrementally mỗi khi có signal mới (view/like/follow).
    tag_preferences: JSON map {tag: weight} dùng cho re-rank online.
    """
    __tablename__ = "user_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    tag_preferences = Column(Text, nullable=True)        # JSON: {"comedy": 0.8, "dance": 0.5}
    interaction_count = Column(Integer, default=0)       # tổng signals (cho cold-start detection)
    last_active_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

