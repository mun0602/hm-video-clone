import classNames from 'classnames/bind';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { memo, useState } from 'react';
import styles from './MobileHeader.module.scss';
import { SearchIcon, LiveIcon, MuteVolumeIcon, UnmuteVolumeIcon, EllipsisIcon, ArrowBackIcon } from '~/assets/images/icons';
import Search from '../Search';
import Menu from '~/components/Popper/Menu';
import { ELLIPSIS_OPTIONS, ELLIPSIS_POPPER_PROPS } from '~/constants/videoConstant';
import { useVolume } from '~/contexts/VolumeContext';

const cx = classNames.bind(styles);

function MobileHeader() {
  const location = useLocation();
  const navigate = useNavigate();
  const { nickname } = useParams();
  
  const isFollowing = location.pathname === '/following';
  const isHome = location.pathname === '/';
  const isProfile = location.pathname.startsWith('/user/');
  const { isGloballyMuted, toggleGlobalMute } = useVolume();
  
  const [showSearch, setShowSearch] = useState(false);

  const menuItems = [
    {
      icon: <SearchIcon />,
      title: 'Tìm kiếm',
      action: 'search',
    },
    ...ELLIPSIS_OPTIONS,
  ];

  return (
    <div className={cx('wrapper', { 'search-mode': showSearch, 'profile-mode': isProfile })}>
      {showSearch ? (
        <div className={cx('search-container')}>
          <Search dropdownMenu={true} responsive={false} searchButton={false} className={cx('mobile-search-input')} />
          <button className={cx('cancel-btn')} onClick={() => setShowSearch(false)}>
            Cancel
          </button>
        </div>
      ) : isProfile ? (
        <>
          {/* Nút Back quay lại */}
          <div className={cx('left-action')}>
            <button className={cx('back-btn')} onClick={() => navigate(-1)}>
              <ArrowBackIcon className={cx('icon')} />
            </button>
          </div>

          {/* Nickname người dùng ở giữa */}
          <div className={cx('profile-title')}>
            <span>{nickname || 'Profile'}</span>
          </div>

          {/* Nút ba chấm tùy chọn bên phải */}
          <div className={cx('right-action')}>
            <button className={cx('ellipsis-btn')}>
              <EllipsisIcon className={cx('icon')} />
            </button>
          </div>
        </>
      ) : (
        <>
          {/* Live Icon & Sound Button ở góc trái */}
          <div className={cx('left-action')}>
            <div className={cx('live-btn')}>
              <LiveIcon className={cx('icon')} />
            </div>
            <button className={cx('sound-btn')} onClick={toggleGlobalMute}>
              {isGloballyMuted ? (
                <MuteVolumeIcon className={cx('icon')} />
              ) : (
                <UnmuteVolumeIcon className={cx('icon')} />
              )}
            </button>
          </div>

          {/* Tabs chuyển đổi Following / For You ở giữa */}
          <div className={cx('tabs')}>
            <Link to="/following" className={cx('tab-item', { active: isFollowing })}>
              <span>Following</span>
            </Link>
            <Link to="/" className={cx('tab-item', { active: isHome || (!isFollowing && !location.pathname.startsWith('/messages') && !location.pathname.includes('/user')) })}>
              <span>For You</span>
            </Link>
          </div>

          {/* Menu 3 chấm (chứa Tìm kiếm) ở góc phải */}
          <div className={cx('right-action')}>
            <Menu
              items={menuItems}
              {...ELLIPSIS_POPPER_PROPS}
              offset={[12, 8]}
              className={cx('ellipsis-popper')}
              onChange={(item) => {
                if (item.action === 'search') {
                  setShowSearch(true);
                }
              }}
              onClick={(e) => {
                e.stopPropagation();
              }}
            >
              <button className={cx('ellipsis-btn')}>
                <EllipsisIcon className={cx('icon')} />
              </button>
            </Menu>
          </div>
        </>
      )}
    </div>
  );
}

export default memo(MobileHeader);
