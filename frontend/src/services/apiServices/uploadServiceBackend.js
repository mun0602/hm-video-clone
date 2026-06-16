/**
 * Upload service (backend) — POST /api/videos/upload với multipart FormData.
 */
import api from '~/services/apiClient';

export async function uploadVideo({ file, title = '', tags = '', onProgress } = {}) {
  const form = new FormData();
  form.append('file', file);
  form.append('title', title);
  form.append('tags', tags);

  // Dùng XHR để support progress callback (fetch không support onProgress)
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const token = localStorage.getItem('hm_token');
    const baseUrl = (
      process.env.REACT_APP_API_URL ||
      process.env.REACT_APP_SUPABASE_URL ||
      'http://localhost:8000'
    ).replace(/\/$/, '');
    const url = `${baseUrl}/api/videos/upload`;

    xhr.open('POST', url, true);
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded * 100) / event.total));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch (e) {
          reject(new Error(`Invalid response: ${xhr.responseText}`));
        }
      } else {
        try {
          const err = JSON.parse(xhr.responseText);
          reject(new Error(err.detail || `HTTP ${xhr.status}`));
        } catch (e) {
          reject(new Error(`HTTP ${xhr.status}: ${xhr.responseText}`));
        }
      }
    };

    xhr.onerror = () => reject(new Error('Network error during upload'));
    xhr.onabort = () => reject(new Error('Upload aborted'));

    xhr.send(form);
  });
}
