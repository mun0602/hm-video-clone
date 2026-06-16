/**
 * useLikeFollow — wrap toggle like/follow qua signal service.
 */
import { useCallback } from 'react';
import { toggleLike, toggleFollow } from '~/services/apiServices/signalService';

export default function useLikeFollow() {
  const onLike = useCallback(async (videoId, currentIsLiked) => {
    const result = await toggleLike(videoId);
    if (result && typeof result.liked === 'boolean') {
      return result.liked;
    }
    // Fallback: nếu API fail, return !currentIsLiked (optimistic)
    return !currentIsLiked;
  }, []);

  const onFollow = useCallback(async (creatorId, currentIsFollowed) => {
    const result = await toggleFollow(creatorId);
    if (result && typeof result.followed === 'boolean') {
      return result.followed;
    }
    return !currentIsFollowed;
  }, []);

  return { onLike, onFollow };
}
