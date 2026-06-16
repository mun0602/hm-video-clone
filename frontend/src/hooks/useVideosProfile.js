import { useState, useEffect, useRef } from 'react';
import api from '~/services/apiClient';

// Custom hook to fetch videos for different tabs
function useVideosProfile(profileId, activeTab) {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(false);

  // Cache to store data for each tab
  const cache = useRef({});
  const currentProfileId = useRef(profileId);

  useEffect(() => {
    // Don't fetch anything if no profileId
    if (!profileId) {
      setVideos([]);
      setLoading(false);
      return;
    }

    // Reset cache if profileId changes
    if (currentProfileId.current !== profileId) {
      cache.current = {};
      currentProfileId.current = profileId;
    }

    // Check if we already have data for this tab
    if (cache.current[activeTab]) {
      setVideos(cache.current[activeTab]);
      setLoading(false);
      return;
    }

    const fetchVideos = async () => {
      setLoading(true);

      try {
        let data = [];

        switch (activeTab) {
          case 'videos':
            data = await api.get(`/api/users/${profileId}/videos?limit=30`);
            break;

          case 'liked':
            // TODO: BE chưa có endpoint /api/users/{id}/liked — fallback empty
            data = [];
            break;

          // Add more cases for other tabs when available
          case 'reposts':
          case 'favourites':
          default:
            data = [];
            break;
        }

        const videoData = Array.isArray(data) ? data : [];
        setVideos(videoData);
        cache.current[activeTab] = videoData; // Cache the data
      } catch (err) {
        console.error(`Error fetching ${activeTab}:`, err);
        setVideos([]);
        cache.current[activeTab] = [];
      } finally {
        setLoading(false);
      }
    };

    fetchVideos();
  }, [profileId, activeTab]);

  return { videos, loading };
}

export default useVideosProfile;

