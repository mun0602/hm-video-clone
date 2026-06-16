import { createContext, useState, useContext, useEffect } from 'react';
import { toast } from 'sonner';
import * as authService from '~/services/apiServices/authServiceBackend';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [showLoginForm, setShowLoginForm] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  // Initial auth check
  useEffect(() => {
    const initAuth = async () => {
      try {
        const u = await authService.checkAuth();
        if (u) {
          setUser(u);
        }
      } catch (error) {
        console.warn('Auth check failed:', error.message);
        setAuthError(error.message);
      } finally {
        setIsLoading(false);
      }
    };
    initAuth();
  }, []);

  const toggleLoginForm = () => {
    setShowLoginForm((prev) => !prev);
    setIsRegistering(false);
  };

  const toggleRegisterMode = () => {
    setIsRegistering((prev) => !prev);
  };

  const login = async (username, password) => {
    try {
      setIsLoading(true);
      setAuthError(null);
      const result = await authService.login(username, password);
      if (result.success) {
        toast.success('Đăng nhập thành công!');
        if (result.user) setUser(result.user);
        setShowLoginForm(false);
        return { success: true };
      }
      setAuthError(result.message);
      return { success: false, message: result.message };
    } catch (error) {
      const msg = 'Đăng nhập thất bại';
      setAuthError(msg);
      return { success: false, message: msg };
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (firstName, lastName, email, password) => {
    try {
      setIsLoading(true);
      setAuthError(null);
      const result = await authService.register(firstName, lastName, email, password);
      if (result.success) {
        toast.success('Đăng ký thành công!');
        if (result.user) setUser(result.user);
        setIsRegistering(false);
        setShowLoginForm(false);
        return { success: true };
      }
      setAuthError(result.message);
      return { success: false, message: result.message };
    } catch (error) {
      const msg = 'Đăng ký thất bại';
      setAuthError(msg);
      return { success: false, message: msg };
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      const result = await authService.logout();
      if (result.success) {
        toast.info('Đã đăng xuất');
        setUser(null);
        window.location.href = '/';
      }
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  const value = {
    user,
    showLoginForm,
    isRegistering,
    isLoading,
    authError,
    toggleLoginForm,
    toggleRegisterMode,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
