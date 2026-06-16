import classNames from 'classnames/bind';
import { Link, useLocation } from 'react-router-dom';
import { useMemo, memo } from 'react';
import styles from './BottomBar.module.scss';
import { useAuth } from '~/contexts/AuthContext';
import {
  HomeIcon,
  HomeSolidIcon,
  FollowingIcon,
  FollowingSolidIcon,
  PlusIcon,
  InboxRegularIcon,
  InboxSolidIcon,
  ProfileIcon,
} from '~/assets/images/icons';

import { DEFAULT_AVATAR } from '~/constants/common';

const cx = classNames.bind(styles);

function BottomBar() {
  const { user, toggleLoginForm } = useAuth();
  const location = useLocation();

  const handleProfileClick = (e) => {
    if (!user) {
      e.preventDefault();
      toggleLoginForm();
    }
  };

  const handleUploadClick = (e) => {
    if (!user) {
      e.preventDefault();
      toggleLoginForm();
    }
  };

  return (
    <div className={cx('wrapper')}>
      <div className={cx('container')}>
        {/* Home */}
        <Link to="/" className={cx('item', { active: location.pathname === '/' })}>
          {location.pathname === '/' ? <HomeSolidIcon className={cx('icon')} /> : <HomeIcon className={cx('icon')} />}
          <span className={cx('label')}>Home</span>
        </Link>

        {/* Following */}
        <Link to="/following" className={cx('item', { active: location.pathname === '/following' })}>
          {location.pathname === '/following' ? <FollowingSolidIcon className={cx('icon')} /> : <FollowingIcon className={cx('icon')} />}
          <span className={cx('label')}>Following</span>
        </Link>

        {/* Upload Button [ + ] */}
        <Link to="/upload" onClick={handleUploadClick} className={cx('item', 'upload-item')}>
          <div className={cx('upload-btn')}>
            <PlusIcon className={cx('plus-icon')} />
          </div>
        </Link>

        {/* Messages */}
        <Link to="/messages" onClick={handleUploadClick} className={cx('item', { active: location.pathname === '/messages' })}>
          {location.pathname === '/messages' ? <InboxSolidIcon className={cx('icon')} /> : <InboxRegularIcon className={cx('icon')} />}
          <span className={cx('label')}>Inbox</span>
        </Link>

        {/* Profile */}
        <Link
          to={user ? `/user/${user.nickname}` : '#'}
          onClick={handleProfileClick}
          className={cx('item', { active: user && location.pathname.startsWith(`/user/${user.nickname}`) })}
        >
          {user ? (
            <img
              src={user.avatar_url || DEFAULT_AVATAR}
              alt="avatar"
              className={cx('avatar')}
              onError={(e) => {
                e.target.onerror = null;
                e.target.src = DEFAULT_AVATAR;
              }}
            />
          ) : (
            <ProfileIcon className={cx('icon')} />
          )}
          <span className={cx('label')}>Profile</span>
        </Link>
      </div>
    </div>
  );
}

export default memo(BottomBar);
