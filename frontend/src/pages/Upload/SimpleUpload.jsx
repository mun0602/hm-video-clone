/**
 * SimpleUpload — minimal upload page dùng BE FastAPI mới.
 * File input → POST /api/videos/upload qua uploadServiceBackend.
 */
import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCloudUploadAlt, faTimes, faCheckCircle } from '@fortawesome/free-solid-svg-icons';
import { uploadVideo } from '~/services/apiServices/uploadServiceBackend';
import { useAuth } from '~/contexts/AuthContext';

function SimpleUpload() {
  const { user, toggleLoginForm } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [title, setTitle] = useState('');
  const [tags, setTags] = useState('');
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  if (!user) {
    return (
      <div className="w-full h-screen flex flex-col items-center justify-center bg-black text-white p-4">
        <h2 className="text-2xl font-bold mb-4">Cần đăng nhập để upload</h2>
        <button
          onClick={toggleLoginForm}
          className="px-6 py-2 bg-gradient-to-r from-pink-500 to-purple-600 rounded-lg"
        >
          Đăng nhập
        </button>
      </div>
    );
  }

  const handleFileSelect = (selected) => {
    if (!selected) return;
    if (!selected.type.startsWith('video/')) {
      setError('File phải là video');
      return;
    }
    setFile(selected);
    setError(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(selected));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) handleFileSelect(f);
  };

  const handleSubmit = async () => {
    if (!file) return;
    setUploading(true);
    setProgress(0);
    setError(null);
    try {
      const result = await uploadVideo({
        file,
        title: title.trim(),
        tags: tags.trim(),
        onProgress: setProgress,
      });
      setSuccess(result);
      setTimeout(() => navigate('/'), 1500);
    } catch (err) {
      setError(err.message || 'Upload thất bại');
    } finally {
      setUploading(false);
    }
  };

  const reset = () => {
    setFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setTitle('');
    setTags('');
    setProgress(0);
    setError(null);
    setSuccess(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  if (success) {
    return (
      <div className="w-full h-screen flex flex-col items-center justify-center bg-black text-white p-4">
        <FontAwesomeIcon icon={faCheckCircle} className="text-6xl text-green-400 mb-4" />
        <h2 className="text-2xl font-bold mb-2">Upload thành công!</h2>
        <p className="text-gray-400">Đang chuyển về trang chủ...</p>
      </div>
    );
  }

  return (
    <div className="w-full min-h-screen bg-black text-white p-4 md:p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">Upload video</h1>

        {!file ? (
          <div
            onClick={() => fileInputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-gray-600 rounded-2xl p-12 text-center cursor-pointer hover:border-pink-500 transition"
          >
            <FontAwesomeIcon icon={faCloudUploadAlt} className="text-6xl text-gray-400 mb-4" />
            <p className="text-lg font-semibold mb-2">Chọn video để upload</p>
            <p className="text-sm text-gray-500">Kéo thả hoặc click. Tối đa 100MB.</p>
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              onChange={(e) => handleFileSelect(e.target.files?.[0])}
              className="hidden"
            />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-start gap-4">
              <video
                src={previewUrl}
                controls
                className="w-48 h-72 object-cover rounded-lg bg-gray-900"
              />
              <div className="flex-1 space-y-3">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Tiêu đề</label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Mô tả video..."
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white"
                    maxLength={200}
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Tags (phân cách bằng dấu phẩy)</label>
                  <input
                    type="text"
                    value={tags}
                    onChange={(e) => setTags(e.target.value)}
                    placeholder="comedy, dance, trending"
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  />
                </div>
              </div>
              <button
                onClick={reset}
                className="p-2 text-gray-400 hover:text-white"
                aria-label="Hủy"
              >
                <FontAwesomeIcon icon={faTimes} />
              </button>
            </div>

            {uploading && (
              <div className="space-y-2">
                <div className="w-full bg-gray-800 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-pink-500 to-purple-600 h-full transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className="text-sm text-gray-400 text-center">{progress}%</p>
              </div>
            )}

            {error && (
              <div className="p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300 text-sm">
                {error}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={uploading}
              className="w-full py-3 bg-gradient-to-r from-pink-500 to-purple-600 rounded-lg font-semibold disabled:opacity-50"
            >
              {uploading ? `Đang upload... ${progress}%` : 'Upload'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default SimpleUpload;
