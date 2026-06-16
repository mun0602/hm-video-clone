// Mock Supabase Client for toptop
// Chuyển hướng toàn bộ các lệnh gọi Supabase sang Backend FastAPI cục bộ chạy tại http://localhost:8000

import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

// Helper để lấy user hiện tại từ LocalStorage
const getStoredSession = () => {
  const sessionStr = localStorage.getItem('supabase_mock_session');
  if (!sessionStr) return null;
  try {
    return JSON.parse(sessionStr);
  } catch (e) {
    return null;
  }
};

const setStoredSession = (session) => {
  if (session) {
    localStorage.setItem('supabase_mock_session', JSON.stringify(session));
    if (session.access_token) {
      localStorage.setItem('hm_token', session.access_token);
    }
  } else {
    localStorage.removeItem('supabase_mock_session');
    localStorage.removeItem('hm_token');
  }
};

const supabase = {
  auth: {
    signInWithPassword: async ({ email, password }) => {
      try {
        const formData = new FormData();
        formData.append('username', email.split('@')[0]);
        formData.append('password', password);

        const response = await axios.post(`${API_BASE}/auth/login`, formData);
        const user = response.data;

        const session = {
          access_token: 'mock-jwt-token-' + user.id,
          user: {
            id: String(user.id),
            email: email,
            user_metadata: {
              fullName: user.display_name,
              nickname: user.username,
              avatar_url: user.avatar_url,
              tick: true
            }
          }
        };

        setStoredSession(session);
        return { data: { session, user: session.user }, error: null };
      } catch (error) {
        const msg = error.response?.data?.detail || error.message;
        return { data: { session: null, user: null }, error: { message: msg } };
      }
    },

    signUp: async ({ email, password, options }) => {
      try {
        const metadata = options?.data || {};
        const fullName = metadata.fullName || email.split('@')[0];
        
        const formData = new FormData();
        formData.append('username', email.split('@')[0]);
        formData.append('password', password);
        formData.append('display_name', fullName);

        const response = await axios.post(`${API_BASE}/auth/register`, formData);
        const user = response.data;

        // Tự động thêm vào bảng user thông qua API table
        await axios.post(`${API_BASE}/table/user/insert`, {
          id: String(user.id),
          email: email,
          nickname: user.username,
          fullName: user.display_name,
          avatar_url: user.avatar_url
        });

        const session = {
          access_token: 'mock-jwt-token-' + user.id,
          user: {
            id: String(user.id),
            email: email,
            user_metadata: {
              fullName: user.display_name,
              nickname: user.username,
              avatar_url: user.avatar_url,
              tick: true
            }
          }
        };

        return { data: { session, user: session.user }, error: null };
      } catch (error) {
        const msg = error.response?.data?.detail || error.message;
        return { data: { session: null, user: null }, error: { message: msg } };
      }
    },

    getSession: async () => {
      const session = getStoredSession();
      return { data: { session }, error: null };
    },

    getUser: async () => {
      const session = getStoredSession();
      if (!session) return { data: { user: null }, error: new Error('No session') };
      return { data: { user: session.user }, error: null };
    },

    signOut: async () => {
      setStoredSession(null);
      return { error: null };
    },

    onAuthStateChange: (callback) => {
      // Mock onAuthStateChange: gọi callback ngay lập tức với session hiện tại
      const session = getStoredSession();
      const event = session ? 'SIGNED_IN' : 'SIGNED_OUT';
      
      // Chờ một chút để app setup xong rồi trigger
      setTimeout(() => {
        try {
          callback(event, session);
        } catch (e) {
          console.error(e);
        }
      }, 100);

      // Trả về đối tượng unsubscribe giả lập
      return {
        data: {
          subscription: {
            unsubscribe: () => {}
          }
        }
      };
    }
  },

  storage: {
    from: (bucketName) => {
      return {
        createSignedUploadUrl: async (fileName) => {
          try {
            const response = await axios.post(`${API_BASE}/storage/signed-url`, {
              fileName,
              bucketName
            });
            return { data: { signedUrl: response.data.signedUrl }, error: null };
          } catch (error) {
            return { data: null, error };
          }
        },

        getPublicUrl: (fileName) => {
          // Trả về url public của file
          if (bucketName === 'covers') {
            return { data: { publicUrl: `${API_BASE.replace('/api', '')}/static/uploads/${fileName}` } };
          }
          return { data: { publicUrl: `${API_BASE.replace('/api', '')}/static/uploads/${fileName}` } };
        },

        upload: async (fileName, fileData, options) => {
          try {
            // Upload trực tiếp dùng PUT (hoặc giả lập Multipart)
            const response = await axios.put(`${API_BASE}/storage/upload-direct?filename=${fileName}&bucket=${bucketName}`, fileData, {
              headers: {
                'Content-Type': options?.contentType || 'application/octet-stream'
              }
            });
            return { data: { path: fileName }, error: null };
          } catch (error) {
            return { data: null, error };
          }
        },

        remove: async (fileNames) => {
          return { error: null };
        }
      };
    }
  },

  rpc: async (functionName, params = {}) => {
    try {
      const session = getStoredSession();
      const current_user_id = session?.user?.id ? parseInt(session.user.id) : null;
      const headers = session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};
      
      // Đính kèm ID người dùng hiện tại vào payload
      const payload = {
        ...params,
        user_id: current_user_id,
        current_user_id: current_user_id
      };

      const response = await axios.post(`${API_BASE}/rpc/${functionName}`, payload, { headers });
      return { data: response.data, error: null };
    } catch (error) {
      console.error(`RPC ${functionName} error:`, error);
      return { data: null, error: { message: error.response?.data?.detail || error.message } };
    }
  },

  from: (tableName) => {
    let filters = {};
    
    const builder = {
      select: (fields = '*') => {
        filters.select = fields;
        return builder;
      },
      eq: (field, value) => {
        filters[field] = value;
        return builder;
      },
      maybeSingle: async () => {
        try {
          const response = await axios.post(`${API_BASE}/table/${tableName}/query`, filters);
          const data = response.data;
          return { data: data && data.length > 0 ? data[0] : null, error: null };
        } catch (error) {
          return { data: null, error };
        }
      },
      single: async () => {
        try {
          const response = await axios.post(`${API_BASE}/table/${tableName}/query`, filters);
          const data = response.data;
          return { data: data && data.length > 0 ? data[0] : null, error: data && data.length > 0 ? null : new Error('No row found') };
        } catch (error) {
          return { data: null, error };
        }
      },
      insert: async (data) => {
        try {
          // data có thể là array hoặc object đơn lẻ
          const payload = Array.isArray(data) ? data[0] : data;
          const response = await axios.post(`${API_BASE}/table/${tableName}/insert`, payload);
          return { data: [response.data], error: null };
        } catch (error) {
          return { data: null, error };
        }
      },
      update: async (data) => {
        try {
          const payload = { ...data, ...filters };
          const response = await axios.post(`${API_BASE}/table/${tableName}/update`, payload);
          return { data: [response.data], error: null };
        } catch (error) {
          return { data: null, error };
        }
      },
      upsert: async (data) => {
        try {
          const payload = Array.isArray(data) ? data[0] : data;
          await axios.post(`${API_BASE}/table/${tableName}/insert`, payload);
          return { data: [payload], error: null };
        } catch (error) {
          return { data: null, error };
        }
      },
      // Hỗ trợ then/catch (giống như Promise)
      then: async (onResolve, onReject) => {
        try {
          const response = await axios.post(`${API_BASE}/table/${tableName}/query`, filters);
          return onResolve({ data: response.data, error: null });
        } catch (error) {
          if (onReject) return onReject(error);
          return onResolve({ data: null, error });
        }
      }
    };

    return builder;
  }
};

export default supabase;
