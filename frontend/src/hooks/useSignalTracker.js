/**
 * useSignalTracker — track watch time của 1 video.
 *
 * Usage:
 *   const { onTimeUpdate, onSkip, onComplete, getCurrentWatch } = useSignalTracker(video);
 *   <video onTimeUpdate={onTimeUpdate} />
 *
 * Khi component unmount HOẶC user skip → gọi trackView qua signalService.
 */
import { useCallback, useEffect, useRef } from 'react';
import { trackView } from '~/services/apiServices/signalService';

export default function useSignalTracker(video) {
  const startTimeRef = useRef(Date.now());
  const lastReportedRef = useRef(0);
  const videoDurationRef = useRef(video?.duration_seconds || null);
  const videoIdRef = useRef(video?.id || null);

  // Reset khi video đổi
  useEffect(() => {
    if (!video) return;
    videoIdRef.current = video.id;
    videoDurationRef.current = video.duration_seconds || null;
    startTimeRef.current = Date.now();
    lastReportedRef.current = 0;
  }, [video?.id]);

  // Track khi user rời trang (unmount, route change, tab close)
  useEffect(() => {
    return () => {
      const watchDuration = Math.floor((Date.now() - startTimeRef.current) / 1000);
      if (videoIdRef.current && watchDuration > 0) {
        // Best-effort, không await
        trackView({
          videoId: videoIdRef.current,
          watchDuration,
          videoDuration: videoDurationRef.current,
          isSkipped: watchDuration < 2,
        });
      }
    };
  }, []);

  const reportNow = useCallback((overrides = {}) => {
    if (!videoIdRef.current) return;
    const watchDuration = overrides.watchDuration ?? Math.floor((Date.now() - startTimeRef.current) / 1000);
    if (watchDuration <= 0) return;
    trackView({
      videoId: videoIdRef.current,
      watchDuration,
      videoDuration: overrides.videoDuration ?? videoDurationRef.current,
      isSkipped: overrides.isSkipped ?? false,
      isRewatched: overrides.isRewatched ?? false,
    });
    lastReportedRef.current = watchDuration;
  }, []);

  const onTimeUpdate = useCallback((e) => {
    const el = e?.target;
    if (!el || !videoIdRef.current) return;
    if (el.duration && !videoDurationRef.current) {
      videoDurationRef.current = Math.floor(el.duration);
    }
    const current = Math.floor(el.currentTime || 0);
    // Report mỗi 5s
    if (current - lastReportedRef.current >= 5) {
      reportNow({ watchDuration: current, isSkipped: false });
    }
  }, [reportNow]);

  const onSkip = useCallback(() => {
    reportNow({ isSkipped: true });
  }, [reportNow]);

  const onComplete = useCallback(() => {
    reportNow({ isRewatched: false });
  }, [reportNow]);

  return { onTimeUpdate, onSkip, onComplete, reportNow };
}
