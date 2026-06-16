import { useEffect, useState, useRef, useCallback } from 'react';
import { useAuth } from '~/contexts/AuthContext';
import { useVolume } from '~/contexts/VolumeContext';
import { getPersonalizedFeed, getExploreFeed } from '~/services/apiServices/feedService';
import useSignalTracker from '~/hooks/useSignalTracker';
import tiktokLogoLoadingGif from '~/assets/images/TiktokLogoLoading.gif';
import VideoActions from '~/pages/Home/components/VideoActions';
import { VideoInfo } from '~/pages/Home/components/VideoPlayer/components';

function VideoItem({ video, isActive }) {
  const { isGloballyMuted } = useVolume();
  const { onTimeUpdate } = useSignalTracker(isActive ? video : null);
  const videoRef = useRef(null);
  const [expandedDescription, setExpandedDescription] = useState(false);

  const toggleDescription = useCallback((e) => {
    if (e) e.stopPropagation();
    setExpandedDescription((prev) => !prev);
  }, []);

  // Reset state khi video đổi
  useEffect(() => {
    setExpandedDescription(false);
  }, [video.id]);

  // Auto play/pause theo isActive
  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    if (isActive) {
      el.muted = isGloballyMuted;
      el.play().catch(() => {/* autoplay blocked - user needs to interact */});
    } else {
      el.pause();
      el.currentTime = 0;
    }
  }, [isActive, isGloballyMuted, video.file_url]);

  return (
    <div className="relative w-full h-full snap-start bg-black flex items-center justify-center">
      <video
        ref={videoRef}
        src={video.file_url}
        poster={video.thumb_url}
        className="w-full h-full object-cover"
        loop
        muted
        playsInline
        autoPlay
        preload="metadata"
        onTimeUpdate={onTimeUpdate}
        onLoadedData={() => {
          // Bắt buộc play khi load xong (mobile cần explicit play call)
          if (isActive) videoRef.current?.play().catch(() => {});
        }}
        onClick={() => {
          if (videoRef.current?.paused) {
            videoRef.current.play();
          } else {
            videoRef.current?.pause();
          }
        }}
      />

      {/* Video Info (User, Description, Tags & Music Marquee) */}
      <VideoInfo
        video={video}
        expandedDescription={expandedDescription}
        toggleDescription={toggleDescription}
      />

      {/* Video Actions (Like, Comment, Share & spinning vinyl disc) */}
      <VideoActions video={video} />
    </div>
  );
}

function Feed() {
  const { user, toggleLoginForm } = useAuth();
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const containerRef = useRef(null);

  const loadFeed = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let data;
      if (user) {
        data = await getPersonalizedFeed({ limit: 20 });
      } else {
        data = await getExploreFeed({ limit: 20 });
      }
      setVideos(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load feed:', err);
      setError(err.message);
      setVideos([]);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadFeed();
  }, [loadFeed]);

  // Detect current video theo scroll position
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handleScroll = () => {
      const index = Math.round(container.scrollTop / container.clientHeight);
      setCurrentIndex(index);
    };
    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, [videos.length]);

  if (loading) {
    return (
      <div className="w-full h-screen flex items-center justify-center bg-black">
        <img src={tiktokLogoLoadingGif} alt="Loading" className="w-20" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-screen flex flex-col items-center justify-center bg-black text-white p-4">
        <p className="text-red-400 mb-4">Lỗi tải feed: {error}</p>
        <button
          onClick={loadFeed}
          className="px-4 py-2 bg-pink-500 rounded-lg"
        >
          Thử lại
        </button>
      </div>
    );
  }

  if (videos.length === 0) {
    return (
      <div className="w-full h-screen flex flex-col items-center justify-center bg-black text-white p-4 text-center">
        <h2 className="text-2xl font-bold mb-2">Chưa có video nào</h2>
        <p className="text-gray-400 mb-4">
          Hãy là người đầu tiên upload video!
        </p>
        {!user && (
          <button
            onClick={toggleLoginForm}
            className="px-6 py-2 bg-gradient-to-r from-pink-500 to-purple-600 rounded-lg"
          >
            Đăng nhập để upload
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="w-full h-screen overflow-y-scroll snap-y snap-mandatory bg-black"
    >
      {videos.map((video, idx) => (
        <div key={video.id} className="w-full h-screen snap-start">
          <VideoItem video={video} isActive={idx === currentIndex} />
        </div>
      ))}
    </div>
  );
}

export default Feed;
