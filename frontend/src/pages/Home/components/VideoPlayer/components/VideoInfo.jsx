import { memo } from 'react';
import PropTypes from 'prop-types';
import classNames from 'classnames/bind';
import { Link } from 'react-router-dom';
import styles from '../VideoPlayer.module.scss';
import { BlueTickIcon } from '~/assets/images/icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faMusic } from '@fortawesome/free-solid-svg-icons';

const cx = classNames.bind(styles);

const VideoInfo = memo(({ video, expandedDescription, toggleDescription }) => {
  const musicTitle = `nhạc nền - @${video.user.nickname} - ${video.description.split('#')[0].trim() || 'Original Sound'}`;

  return (
    <div className={cx('video-info')}>
      <div className={cx('user-info')}>
        <Link to={`/user/${video.user.nickname}`} className={cx('username')}>
          @{video.user.nickname}
        </Link>
        {video.user.tick && (
          <span className={cx('verified-icon')}>
            <BlueTickIcon />
          </span>
        )}
      </div>

      <div
        className={cx('description', {
          expanded: expandedDescription,
        })}
      >
        <p>
          {video.description.split(/(\s+)/).map((word, index) =>
            word.startsWith('#') ? (
              <strong key={index} className={cx('hashtag')}>
                {word}
              </strong>
            ) : (
              word
            ),
          )}
        </p>
        <strong className={cx('more-btn')} onClick={toggleDescription}>
          {expandedDescription ? 'less' : 'more'}
        </strong>
      </div>

      {/* Nhạc nền kiểu TikTok */}
      <div className={cx('music-info')}>
        <FontAwesomeIcon icon={faMusic} className={cx('music-icon')} />
        <div className={cx('music-ticker')}>
          <div className={cx('music-ticker-wrapper')}>
            <span>{musicTitle}</span>
            <span>{musicTitle}</span>
          </div>
        </div>
      </div>
    </div>
  );
});

VideoInfo.displayName = 'VideoInfo';

VideoInfo.propTypes = {
  video: PropTypes.object.isRequired,
  expandedDescription: PropTypes.bool.isRequired,
  toggleDescription: PropTypes.func.isRequired,
};

export default VideoInfo;
