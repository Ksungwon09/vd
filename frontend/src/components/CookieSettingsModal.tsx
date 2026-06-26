import React, { useState, useEffect } from 'react';
import api from '../api';

import './CookieSettingsModal.css';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSaveSuccess: () => void;
}

const CookieSettingsModal: React.FC<Props> = ({ isOpen, onClose, onSaveSuccess }) => {
  const [cookieContent, setCookieContent] = useState('');
  const [loading, setLoading]             = useState(false);
  const [error, setError]                 = useState('');
  const [hasCookies, setHasCookies]       = useState(false);
  const [hasGoogleAuth, setHasGoogleAuth] = useState(false);

  useEffect(() => {
    if (isOpen) {
      checkStatus();
    }
  }, [isOpen]);

  const checkStatus = async () => {
    try {
      const res = await api.get('/video/cookies/status');
      setHasCookies(res.data.has_cookies);
      setHasGoogleAuth(res.data.has_google_auth);
    } catch (err) {
      console.error('상태 확인 실패', err);
    }
  };

  const handleSave = async () => {
    if (!cookieContent.trim()) {
      setError('쿠키 내용을 입력해주세요.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await api.post('/video/cookies', { content: cookieContent });
      setCookieContent('');
      await checkStatus();
      onSaveSuccess();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || '쿠키 저장에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    setLoading(true);
    setError('');
    try {
      await api.delete('/video/cookies');
      setCookieContent('');
      setHasCookies(false);
    } catch {
      setError('쿠키 삭제에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="cookie-modal-overlay">
      <div className="cookie-modal-content">
        <h2>인증 설정</h2>

        {/* Google OAuth2 상태 */}
        <div className={`cookie-status-${hasGoogleAuth ? 'active' : 'inactive'}`}>
          {hasGoogleAuth
            ? '✅ Google 계정 인증이 연결됐습니다. yt-dlp에 Bearer 토큰이 자동으로 사용됩니다.'
            : '⚠️ Google 인증이 연결되지 않았습니다.'}
        </div>

        <hr style={{ margin: '12px 0', borderColor: '#e5e7eb' }} />

        <p className="cookie-modal-desc">
          <strong>(선택사항)</strong> 비공개 영상 또는 연령 제한 콘텐츠를 위해
          브라우저의 YouTube 쿠키(cookies.txt 형식)를 추가로 업로드할 수 있습니다.
          <br />
          Google 계정 인증만으로도 대부분의 공개 영상을 다운로드할 수 있습니다.
        </p>

        {hasCookies && (
          <div className="cookie-status-active">
            ✅ 추가 쿠키 파일이 저장돼 있습니다. 새로 입력하면 덮어씁니다.
          </div>
        )}

        <textarea
          value={cookieContent}
          onChange={(e) => setCookieContent(e.target.value)}
          placeholder="# Netscape HTTP Cookie File&#10;# (선택 사항)"
          className="cookie-textarea"
          rows={8}
        />

        {error && <div className="cookie-error">{error}</div>}

        <div className="cookie-modal-actions">
          {hasCookies && (
            <button className="cookie-btn-delete" onClick={handleDelete} disabled={loading}>
              쿠키 파일 삭제
            </button>
          )}
          <button className="cookie-btn-cancel" onClick={onClose} disabled={loading}>
            닫기
          </button>
          <button className="cookie-btn-save" onClick={handleSave} disabled={loading}>
            {loading ? '저장 중...' : '쿠키 저장'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CookieSettingsModal;
