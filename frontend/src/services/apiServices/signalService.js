/**
 * Signal tracking service — gọi BE FastAPI /api/signals/* endpoints.
 * Dùng cho: view (watch time + skip), like toggle, follow toggle.
 */
import api from '~/services/apiClient';

export async function trackView({ videoId, watchDuration, videoDuration, isSkipped = false, isRewatched = false }) {
  try {
    return await api.post('/api/signals/view', {
      video_id: videoId,
      watch_duration: watchDuration,
      video_duration: videoDuration ?? null,
      is_skipped: isSkipped,
      is_rewatched: isRewatched,
    });
  } catch (error) {
    console.warn('[signal] trackView failed:', error.message);
    return null;
  }
}

export async function toggleLike(videoId) {
  try {
    return await api.post('/api/signals/like', { video_id: videoId });
  } catch (error) {
    console.warn('[signal] toggleLike failed:', error.message);
    return null;
  }
}

export async function toggleFollow(followingId) {
  try {
    return await api.post('/api/signals/follow', { following_id: followingId });
  } catch (error) {
    console.warn('[signal] toggleFollow failed:', error.message);
    return null;
  }
}
