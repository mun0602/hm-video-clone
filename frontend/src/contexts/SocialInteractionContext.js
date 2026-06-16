import { createContext, useState, useContext, useEffect, useCallback } from 'react';
import { useAuth } from './AuthContext';
import { toggleLike, toggleFollow } from '~/services/apiServices/signalService';
import api from '~/services/apiClient';

const SocialInteractionContext = createContext();

export const useSocialInteraction = () => useContext(SocialInteractionContext);

export const SocialInteractionProvider = ({ children }) => {
  const { user } = useAuth();
  const [followingIds, setFollowingIds] = useState([]);
  const [followersIds, setFollowersIds] = useState([]);
  const [followingUsers, setFollowingUsers] = useState({});
  const [followersUsers, setFollowersUsers] = useState({});
  const [isLoading, setIsLoading] = useState(false);

  // Load following list khi user login
  useEffect(() => {
    if (user) {
      fetchFollowingData();
      fetchFollowersData();
    } else {
      setFollowingIds([]);
      setFollowersIds([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const fetchFollowingData = async () => {
    try {
      const ids = await api.get('/api/users/me/following-ids');
      setFollowingIds(Array.isArray(ids) ? ids : []);
    } catch (error) {
      console.error('Error loading following ids:', error);
    }
  };

  const fetchFollowersData = async () => {
    try {
      const ids = await api.get('/api/users/me/followers-ids');
      setFollowersIds(Array.isArray(ids) ? ids : []);
    } catch (error) {
      console.error('Error loading followers ids:', error);
    }
  };

  const fetchFollowingUsers = useCallback(
    async (userId) => {
      if (followingUsers[userId]) return followingUsers[userId];
      try {
        setIsLoading(true);
        const data = await api.get('/api/users/me/following');
        setFollowingUsers((prev) => ({ ...prev, [userId]: data || [] }));
        return data || [];
      } catch (error) {
        console.error('Error calling get_following users:', error);
        return [];
      } finally {
        setIsLoading(false);
      }
    },
    [followingUsers],
  );

  const fetchFollowersUsers = useCallback(
    async (userId) => {
      if (followersUsers[userId]) return followersUsers[userId];
      try {
        setIsLoading(true);
        const data = await api.get('/api/users/me/followers');
        setFollowersUsers((prev) => ({ ...prev, [userId]: data || [] }));
        return data || [];
      } catch (error) {
        console.error('Error calling get_followers users:', error);
        return [];
      } finally {
        setIsLoading(false);
      }
    },
    [followersUsers],
  );

  const handleToggleFollow = async (targetUserId) => {
    try {
      const result = await toggleFollow(targetUserId);
      // result: { followed: true|false }
      if (result && typeof result.followed === 'boolean') {
        setFollowingIds((prev) => {
          if (result.followed) {
            return prev.includes(targetUserId) ? prev : [...prev, targetUserId];
          }
          return prev.filter((id) => id !== targetUserId);
        });
        return result.followed;
      }
      return null;
    } catch (error) {
      console.error('Toggle follow error:', error);
      throw error;
    }
  };

  const handleToggleLikeVideo = async (targetVideoId) => {
    try {
      const result = await toggleLike(targetVideoId);
      return result;
    } catch (error) {
      console.error('Toggle like error:', error);
      throw error;
    }
  };

  const isFollowing = useCallback(
    (targetUserId) => {
      if (!targetUserId || !followingIds) return false;
      return followingIds.includes(targetUserId);
    },
    [followingIds],
  );

  const value = {
    isLoading,
    isFollowing,
    followingIds,
    followersIds,
    followingUsers,
    followersUsers,
    fetchFollowersData,
    fetchFollowingUsers,
    fetchFollowersUsers,
    handleToggleFollow,
    handleToggleLikeVideo,
  };

  return (
    <SocialInteractionContext.Provider value={value}>
      {children}
    </SocialInteractionContext.Provider>
  );
};
