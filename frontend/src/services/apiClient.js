/**
 * apiClient.js — thin wrapper quanh fetch() để gọi FastAPI backend.
 * Tự động gắn Authorization header từ localStorage token.
 * Trả về JSON hoặc throw Error với message từ server.
 */

const API_BASE_URL = (
  process.env.REACT_APP_API_URL ||
  process.env.REACT_APP_SUPABASE_URL ||
  'http://localhost:8000'
).replace(/\/$/, '');

const TOKEN_KEY = 'hm_token';

// Helper đệ quy chuẩn hóa URL tĩnh thành relative path
function normalizeUrls(obj) {
  if (!obj) return obj;
  if (typeof obj === 'string') {
    if (obj.startsWith('http') && obj.includes('/static/uploads/')) {
      const index = obj.indexOf('/static/uploads/');
      return obj.substring(index);
    }
    return obj;
  }
  if (Array.isArray(obj)) {
    return obj.map(normalizeUrls);
  }
  if (typeof obj === 'object') {
    const newObj = {};
    for (const key in obj) {
      newObj[key] = normalizeUrls(obj[key]);
    }
    return newObj;
  }
  return obj;
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function clearToken() {
  return localStorage.removeItem(TOKEN_KEY);
}

/**
 * Core fetch wrapper.
 * @param {string} path  - ví dụ "/api/feed"
 * @param {object} options - { method, body, headers, signal }
 * @returns {Promise<any>} parsed JSON
 */
export async function apiFetch(path, { method = 'GET', body, headers = {}, signal, isForm = false } = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`;

  const finalHeaders = { ...headers };
  if (!isForm && body && !(body instanceof FormData)) {
    finalHeaders['Content-Type'] = 'application/json';
  }
  const token = getToken();
  if (token) {
    finalHeaders['Authorization'] = `Bearer ${token}`;
  }

  const fetchOptions = {
    method,
    headers: finalHeaders,
    signal,
  };
  if (body) {
    if (isForm || body instanceof FormData) {
      fetchOptions.body = body;
    } else {
      fetchOptions.body = JSON.stringify(body);
    }
  }

  const response = await fetch(url, fetchOptions);

  // 204 No Content
  if (response.status === 204) {
    return null;
  }

  // Try to parse JSON (may fail on empty body)
  let data = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    data = await response.json().catch(() => null);
  } else {
    data = await response.text().catch(() => null);
  }

  if (!response.ok) {
    const detail =
      (data && typeof data === 'object' && data.detail) ||
      (typeof data === 'string' && data) ||
      `HTTP ${response.status}`;
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    err.status = response.status;
    err.data = data;
    throw err;
  }

  return normalizeUrls(data);
}

// ============================================================
// Convenience methods
// ============================================================

export const api = {
  get: (path, opts) => apiFetch(path, { ...opts, method: 'GET' }),
  post: (path, body, opts) => apiFetch(path, { ...opts, method: 'POST', body }),
  put: (path, body, opts) => apiFetch(path, { ...opts, method: 'PUT', body }),
  patch: (path, body, opts) => apiFetch(path, { ...opts, method: 'PATCH', body }),
  delete: (path, opts) => apiFetch(path, { ...opts, method: 'DELETE' }),
};

export default api;
