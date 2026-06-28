import React, { useState, useEffect } from 'react';
import api from '../api';
import './CookieSettingsModal.css';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSaveSuccess: () => void;
}

interface AuthStatus {
  has_cookies: boolean;
  has_google_auth: boolean;
  has_tv_cookies: boolean;
  auth_method: 'tv_oauth' | 'cookie' | 'none';
}

const CookieSettingsModal: React.FC<Props> = ({ isOpen, onClose, onSaveSuccess }) => {
  const [tab, setTab]                   = useState<'tv' | 'manual'>('tv');
  const [cookieContent, setCookieContent] = useState('');
  const [loading, setLoading]           = useState(false);
  const [tvLoading, setTvLoading]       = useState(false);
  const [error, setError]               = useState('');
  const [tvError, setTvError]           = useState('');
  const [tvSuccess, setTvSuccess]       = useState('');
  const [status, setStatus]             = useState<AuthStatus | null>(null);

  useEffect(() => {
    if (isOpen) {
      checkStatus();
      setError('');
      setTvError('');
      setTvSuccess('');
    }
  }, [isOpen]);

  const checkStatus = async () => {
    try {
      const res = await api.get('/video/cookies/status');
      setStatus(res.data);
    } catch (err) {
      console.error('상태 확인 실패', err);
    }
  };

  // ── TV 인증: Google OAuth2 토큰으로 YouTube 쿠키 자동 획득 ────────────────
  const handleFetchTvCookies = async () => {
    setTvLoading(true);
    setTvError('');
    setTvSuccess('');
    try {
      const res = await api.post('/video/tv-auth/fetch');
      setTvSuccess(
        `✅ YouTube TV 인증 완료! ${res.data.cookie_count}개 쿠키를 획득했습니다.\n` +
        `획득 쿠키: ${res.data.cookies_acquired.join(', ')}`
      );
      await checkStatus();
      onSaveSuccess();
    } catch (err: any) {
      setTvError(err.response?.data?.detail || 'TV 인증 쿠키 획득에 실패했습니다.');
    } finally {
      setTvLoading(false);
    }
  };

  const handleDeleteTvCookies = async () => {
    setTvLoading(true);
    setTvError('');
    try {
      await api.delete('/video/tv-auth');
      setTvSuccess('TV 인증 쿠키가 삭제되었습니다.');
      await checkStatus();
    } catch {
      setTvError('쿠키 삭제에 실패했습니다.');
    } finally {
      setTvLoading(false);
    }
  };

  // ── 수동 쿠키 저장 ──────────────────────────────────────────────────────
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
      await checkStatus();
    } catch {
      setError('쿠키 삭제에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const authMethodLabel = () => {
    if (!status) return null;
    if (status.auth_method === 'tv_oauth')
      return <span className="auth-badge auth-badge--tv">🔐 TV OAuth 인증 활성</span>;
    if (status.auth_method === 'cookie')
      return <span className="auth-badge auth-badge--cookie">🍪 수동 쿠키 활성</span>;
    return <span className="auth-badge auth-badge--none">⚠️ 인증 없음</span>;
  };

  return (
    <div className="cookie-modal-overlay">
      <div className="cookie-modal-content">
        <div className="cookie-modal-header">
          <h2>YouTube 인증 설정</h2>
          {authMethodLabel()}
        </div>

        {/* 탭 */}
        <div className="cookie-tabs">
          <button
            className={`cookie-tab ${tab === 'tv' ? 'cookie-tab--active' : ''}`}
            onClick={() => setTab('tv')}
          >
            🔐 TV 자동 인증 <span className="cookie-tab-badge">권장</span>
          </button>
          <button
            className={`cookie-tab ${tab === 'manual' ? 'cookie-tab--active' : ''}`}
            onClick={() => setTab('manual')}
          >
            🍪 수동 쿠키
          </button>
        </div>

        {/* TV 인증 탭 */}
        {tab === 'tv' && (
          <div className="cookie-tab-panel">
            <div className="tv-auth-desc">
              <p>
                <strong>YouTube TV 자동 인증</strong>은 이미 연결된 Google 계정을 활용하여
                YouTube 인증 쿠키를 자동으로 획득합니다.
              </p>
              <ul>
                <li>✅ 별도 쿠키 파일 내보내기 불필요</li>
                <li>✅ <code>tv</code> 클라이언트로 고화질 포맷 접근</li>
                <li>✅ YouTube 봇 감지 우회에 효과적</li>
                <li>⚠️ Google 계정이 연결되어 있어야 합니다</li>
              </ul>
            </div>

            {status && (
              <div className={`tv-auth-status ${status.has_google_auth ? 'status--ok' : 'status--warn'}`}>
                {status.has_google_auth
                  ? '✅ Google 계정이 연결되어 있습니다.'
                  : '❌ Google 계정이 연결되지 않았습니다. Google로 로그인해주세요.'}
              </div>
            )}

            {status?.has_tv_cookies && (
              <div className="tv-auth-status status--ok">
                ✅ YouTube TV 인증 쿠키가 저장되어 있습니다. 다운로드에 자동 사용됩니다.
              </div>
            )}

            {tvError && <div className="cookie-error">{tvError}</div>}
            {tvSuccess && <div className="cookie-success" style={{ whiteSpace: 'pre-line' }}>{tvSuccess}</div>}

            <div className="cookie-modal-actions">
              {status?.has_tv_cookies && (
                <button
                  className="cookie-btn-delete"
                  onClick={handleDeleteTvCookies}
                  disabled={tvLoading}
                >
                  쿠키 삭제
                </button>
              )}
              <button className="cookie-btn-cancel" onClick={onClose} disabled={tvLoading}>
                닫기
              </button>
              <button
                className="cookie-btn-save"
                onClick={handleFetchTvCookies}
                disabled={tvLoading || !status?.has_google_auth}
              >
                {tvLoading ? '인증 중...' : status?.has_tv_cookies ? '쿠키 갱신' : 'YouTube 인증하기'}
              </button>
            </div>
          </div>
        )}

        {/* 수동 쿠키 탭 */}
        {tab === 'manual' && (
          <div className="cookie-tab-panel">
            <p className="cookie-modal-desc">
              브라우저 확장 프로그램(Get cookies.txt LOCALLY 등)으로 내보낸
              YouTube 쿠키 파일을 직접 붙여넣습니다.
            </p>

            {status?.has_cookies && (
              <div className="cookie-status-active">
                ✅ 수동 쿠키 파일이 저장돼 있습니다. 새로 입력하면 덮어씁니다.
              </div>
            )}

            <textarea
              value={cookieContent}
              onChange={(e) => setCookieContent(e.target.value)}
              placeholder="# Netscape HTTP Cookie File&#10;# (cookies.txt 내용 붙여넣기)"
              className="cookie-textarea"
              rows={8}
            />

            {error && <div className="cookie-error">{error}</div>}

            <div className="cookie-modal-actions">
              {status?.has_cookies && (
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
        )}
      </div>
    </div>
  );
};

export default CookieSettingsModal;
