import config from '~/config';

// Layouts
import { HeaderOnly } from '~/layouts';

// Pages — dùng Feed mới + SimpleUpload thay cho các page cũ phụ thuộc Supabase
import Feed from '~/pages/Feed';
import SimpleUpload from '~/pages/Upload/SimpleUpload';
import Profile from '~/pages/Profile';
import Settings from '~/pages/Settings';
import Following from '~/pages/Following';
import Live from '~/pages/Live';
import Messages from '~/pages/Messages';
import ResetPassword from '~/pages/ResetPassword';

const publicRoutes = [
  { path: config.routes.home, component: Feed },
  { path: config.routes.following, component: Following },
  {
    path: config.routes.setting,
    component: Settings,
    layout: HeaderOnly,
    requireAuth: true,
  },
  {
    path: config.routes.upload,
    component: SimpleUpload,
    layout: HeaderOnly,
    requireAuth: true,
  },
  { path: config.routes.messages, component: Messages, requireAuth: true },
  { path: config.routes.live, component: Live },
  { path: config.routes.profile, component: Profile },
  {
    path: config.routes.resetPassword,
    component: ResetPassword,
    layout: HeaderOnly,
  },
];

const privateRoutes = [];

export { publicRoutes, privateRoutes };
