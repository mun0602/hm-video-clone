import React, { createContext, useState, useEffect, useCallback } from 'react';

const VolumeContext = createContext();

/**
 * VolumeProvider — quản lý trạng thái âm thanh.
 *
 * Theo yêu cầu Mun ca: popup mỗi lần vào (no memory).
 * Tuy nhiên context vẫn giữ state trong session để:
 * - User chọn "bật" trong popup → tất cả video phát có tiếng
 * - User click nút mute/unmute trên video → cập nhật
 *
 * Lắng nghe event 'hm:audio-decided' từ AudioOnboarding để set initial state.
 */
export const VolumeProvider = ({ children }) => {
  const [isGloballyMuted, setIsGloballyMuted] = useState(true); // default muted

  useEffect(() => {
    const handler = (e) => {
      if (e.detail && typeof e.detail.enabled === 'boolean') {
        setIsGloballyMuted(!e.detail.enabled);
      }
    };
    window.addEventListener('hm:audio-decided', handler);
    return () => window.removeEventListener('hm:audio-decided', handler);
  }, []);

  const toggleGlobalMute = useCallback(() => {
    setIsGloballyMuted((prev) => !prev);
  }, []);

  return (
    <VolumeContext.Provider value={{ isGloballyMuted, toggleGlobalMute }}>
      {children}
    </VolumeContext.Provider>
  );
};

export const useVolume = () => {
  const context = React.useContext(VolumeContext);
  if (context === undefined) {
    throw new Error('useVolume must be used within a VolumeProvider');
  }
  return context;
};
