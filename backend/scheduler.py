"""APScheduler setup: chạy offline job build feed_cache mỗi vài giờ.

In-process scheduler. Restart service = mất scheduled jobs (acceptable cho scale này).
Production scale có thể chuyển sang Celery + Redis.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from recommender import feed_cache

logger = logging.getLogger(__name__)

# Interval giữa 2 lần build (giờ)
FEED_REBUILD_INTERVAL_HOURS = 2

_scheduler: BackgroundScheduler = None


def _build_all_feeds_job():
    """Job được scheduler gọi định kỳ."""
    try:
        summary = feed_cache.build_feed_for_all_users()
        logger.info(f"Scheduled feed rebuild: {summary}")
    except Exception:
        logger.exception("Scheduled feed rebuild failed")


def start_scheduler():
    """Khởi động scheduler. Gọi 1 lần khi FastAPI startup."""
    global _scheduler
    if _scheduler is not None:
        logger.warning("Scheduler already started, skipping")
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _build_all_feeds_job,
        trigger=IntervalTrigger(hours=FEED_REBUILD_INTERVAL_HOURS),
        id="build_feeds",
        name="Build feed cache cho tất cả users",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info(f"Scheduler started: feed rebuild every {FEED_REBUILD_INTERVAL_HOURS}h")


def stop_scheduler():
    """Dừng scheduler (gọi khi FastAPI shutdown)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


def trigger_immediate_build():
    """Trigger 1 lần build ngay (test hoặc admin endpoint)."""
    _build_all_feeds_job()
