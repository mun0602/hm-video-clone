/**
 * AudioOnboarding popup — hiển thị mỗi lần vào web, hỏi user muốn bật/tắt âm thanh.
 * Theo yêu cầu Mun ca: "popup mỗi lần vào (no memory)" → không lưu preference.
 * Sau khi user chọn → dispatch event để VolumeContext biết initial state.
 */
import { useEffect, useState } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faVolumeHigh, faVolumeXmark } from '@fortawesome/free-solid-svg-icons';

const STORAGE_KEY = 'hm_audio_onboarded'; // chỉ dùng để KHÔNG hiển thị liên tục khi user vừa chọn xong

export default function AudioOnboarding() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    // Hiển thị mỗi lần load (no memory). Dùng sessionStorage để tránh flash khi re-render.
    // Khi user đóng tab → mở lại → popup lại hiện.
    setOpen(true);

    // Dispatch event cho VolumeContext (nếu có) lắng nghe
    const handler = (e) => {
      if (e.detail && typeof e.detail.enabled === 'boolean') {
        // No-op: state đã được set qua setOpen(false) ở onChoose
      }
    };
    window.addEventListener('hm:audio-decided', handler);
    return () => window.removeEventListener('hm:audio-decided', handler);
  }, []);

  const onChoose = (enabled) => {
    // Dispatch global event để VideoPlayer / VolumeProvider biết
    window.dispatchEvent(new CustomEvent('hm:audio-decided', { detail: { enabled } }));
    setOpen(false);
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="audio-onboarding-title"
    >
      <div className="bg-white rounded-2xl shadow-2xl w-[90%] max-w-sm p-6 mx-4 animate-[fadeIn_0.2s_ease-out]">
        <div className="flex justify-center mb-4">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-pink-500 to-purple-600 flex items-center justify-center">
            <FontAwesomeIcon icon={faVolumeHigh} className="text-white text-2xl" />
          </div>
        </div>

        <h2
          id="audio-onboarding-title"
          className="text-xl font-bold text-center text-gray-900 mb-2"
        >
          Bật âm thanh?
        </h2>
        <p className="text-center text-gray-600 text-sm mb-6">
          Chọn có muốn bật âm thanh cho video hay không. Bạn có thể đổi ý bất cứ lúc nào bằng biểu tượng loa trên video.
        </p>

        <div className="flex flex-col gap-3">
          <button
            onClick={() => onChoose(true)}
            className="w-full py-3 px-4 bg-gradient-to-r from-pink-500 to-red-500 text-white font-semibold rounded-lg hover:opacity-90 active:scale-95 transition flex items-center justify-center gap-2"
            autoFocus
          >
            <FontAwesomeIcon icon={faVolumeHigh} />
            <span>Bật âm thanh</span>
          </button>
          <button
            onClick={() => onChoose(false)}
            className="w-full py-3 px-4 bg-gray-100 text-gray-700 font-semibold rounded-lg hover:bg-gray-200 active:scale-95 transition flex items-center justify-center gap-2"
          >
            <FontAwesomeIcon icon={faVolumeXmark} />
            <span>Để im lặng</span>
          </button>
        </div>
      </div>
    </div>
  );
}
