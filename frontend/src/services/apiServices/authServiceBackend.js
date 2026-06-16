/**
 * Backend auth service — gọi FastAPI JWT endpoints thay vì Supabase.
 * Compatible shape với authService.js cũ (return { success, user, ... }).
 */
import api, { setToken, clearToken, getToken } from '~/services/apiClient';

// BE login form expects: username + password
// BE register form expects: username + password + display_name

// Normalize: LoginForm submit email ("tester@gmail.com") nhưng BE cần username thuần ("tester")
const _normalizeUsername = (raw) => {
  if (!raw) return raw;
  // Nếu có @ → lấy phần trước @
  if (raw.includes('@')) return raw.split('@')[0];
  return raw;
};

export const login = async (usernameOrEmail, password) => {
  try {
    const username = _normalizeUsername(usernameOrEmail);
    const form = new FormData();
    form.append('username', username);
    form.append('password', password);

    const data = await api.post('/api/auth/login', form, { isForm: true });

    if (data && data.access_token) {
      setToken(data.access_token);
    }
    return {
      success: true,
      user: {
        id: String(data.id),
        username: data.username,
        nickname: data.username,
        fullName: data.display_name,
        display_name: data.display_name,
        avatar_url: data.avatar_url,
        bio: data.bio,
      },
      access_token: data.access_token,
    };
  } catch (error) {
    return { success: false, message: error.message || 'Login failed' };
  }
};

export const register = async (firstName, lastName, email, password) => {
  try {
    // Map email → username (BE dùng username, không có email)
    const username = email.split('@')[0];
    const displayName = `${firstName} ${lastName}`.trim();

    const form = new FormData();
    form.append('username', username);
    form.append('password', password);
    form.append('display_name', displayName);

    const data = await api.post('/api/auth/register', form, { isForm: true });

    // Auto-login sau register
    return await login(username, password);
  } catch (error) {
    return { success: false, message: error.message || 'Registration failed' };
  }
};

export const checkAuth = async () => {
  const token = getToken();
  if (!token) return null;

  // Verify token + lấy full profile qua endpoint /api/auth/me
  try {
    const data = await api.get('/api/auth/me');
    if (!data) return null;
    return {
      id: String(data.id),
      username: data.username,
      nickname: data.nickname || data.username,
      fullName: data.display_name,
      display_name: data.display_name,
      avatar_url: data.avatar_url,
      bio: data.bio,
    };
  } catch (error) {
    if (error.status === 401) {
      clearToken();
      return null;
    }
    throw error;
  }
};

export const logout = async () => {
  clearToken();
  return { success: true };
};

export const getSession = async () => {
  const token = getToken();
  if (!token) return null;
  return { access_token: token };
};

export const onAuthStateChange = (callback) => {
  // BE không có realtime auth — wrap thành 1 lần initial check
  let mounted = true;
  (async () => {
    const user = await checkAuth();
    if (mounted) {
      callback(user ? 'SIGNED_IN' : 'SIGNED_OUT', user);
    }
  })();
  return {
    data: {
      subscription: {
        unsubscribe: () => {
          mounted = false;
        },
      },
    },
  };
};

// Stubs để giữ tương thích với code cũ gọi các hàm này
export const checkEmailExists = async () => false;
export const sendPasswordResetEmail = async () => ({ success: false, message: 'Not supported' });
export const updatePassword = async () => ({ success: false, message: 'Not supported' });
export const refreshSession = async () => ({ success: false, message: 'Not supported' });
export const resendEmailVerification = async () => ({ success: false, message: 'Not supported' });
