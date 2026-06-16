/**
 * Feed service — personalized & explore feeds.
 */
import api from '~/services/apiClient';

export async function getPersonalizedFeed({ limit = 20, offset = 0 } = {}) {
  return api.get(`/api/feed?limit=${limit}&offset=${offset}`);
}

export async function getExploreFeed({ limit = 20, offset = 0 } = {}) {
  return api.get(`/api/feed/explore?limit=${limit}&offset=${offset}`);
}

export async function getVideoById(videoId) {
  return api.get(`/api/videos/${videoId}`);
}

export async function getVideosByCreator(userId, { limit = 20, offset = 0 } = {}) {
  return api.get(`/api/videos/by-creator/${userId}?limit=${limit}&offset=${offset}`);
}
