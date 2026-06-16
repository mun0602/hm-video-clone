import './styles/tailwind.css';
import { Fragment } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useLocation,
} from 'react-router-dom';
import { Toaster } from 'sonner';
import { publicRoutes } from './routes';
import DefaultLayout from '~/layouts';
import {
  AutoScrollProvider,
  AuthProvider,
  SocialInteractionProvider,
  VolumeProvider,
  PresenceProvider,
} from './contexts';
import { useAuth } from './contexts/AuthContext';
import usePresenceCleanup from './hooks/usePresenceCleanup';
import LoginForm from './components/LoginForm';
import AuthErrorHandler from './components/AuthErrorHandler';
import AudioOnboarding from './components/AudioOnboarding';
import config from '~/config';
import tiktokLogoLoadingGif from './assets/images/TiktokLogoLoading.gif';

// Component để bảo vệ routes
const ProtectedRoute = ({ children, requireAuth = false }) => {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="w-[88px] h-auto bg-white absolute top-[50%] left-[50%] translate-x-[-50%] translate-y-[-50%]">
        <img src={tiktokLogoLoadingGif} alt="Loading" />
      </div>
    );
  }

  if (requireAuth && !user) {
    return <Navigate to={config.routes.home} replace />;
  }

  return children;
};

const PresenceCleanupManager = () => {
  usePresenceCleanup();
  return null;
};

const AppContent = () => {
  return (
    <AuthErrorHandler>
      <div>
        <PresenceCleanupManager />
        <LoginForm />
        {/* Audio onboarding popup: hiển thị mỗi lần vào web (no memory) */}
        <AudioOnboarding />
        <Routes>
          {publicRoutes.map((route, index) => {
            const Page = route.component;
            let Layout = DefaultLayout;

            if (route.layout) {
              Layout = route.layout;
            } else if (route.layout === null) {
              Layout = Fragment;
            }

            const requireAuth = route.requireAuth || false;

            return (
              <Route
                key={index}
                path={route.path}
                element={
                  <ProtectedRoute requireAuth={requireAuth}>
                    <AutoScrollProvider>
                      <VolumeProvider>
                        <Layout>
                          <Page />
                        </Layout>
                      </VolumeProvider>
                    </AutoScrollProvider>
                  </ProtectedRoute>
                }
              />
            );
          })}
        </Routes>
      </div>
    </AuthErrorHandler>
  );
};

function App() {
  return (
    <AuthProvider>
      <PresenceProvider>
        <SocialInteractionProvider>
          <Router>
            <AppContent />
            <Toaster position="top-center" richColors />
          </Router>
        </SocialInteractionProvider>
      </PresenceProvider>
    </AuthProvider>
  );
}

export default App;
