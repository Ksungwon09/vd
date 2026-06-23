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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [hasCookies, setHasCookies] = useState(false);

  useEffect(() => {
    if (isOpen) {
      checkCookieStatus();
    }
  }, [isOpen]);

  const checkCookieStatus = async () => {
    try {
      const res = await api.get('/video/cookies/status');
      setHasCookies(res.data.has_cookies);
    } catch (err) {
      console.error('Failed to check cookie status', err);
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
      await checkCookieStatus();
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
    } catch (err: any) {
      setError('쿠키 삭제에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="cookie-modal-overlay">
      <div className="cookie-modal-content">
        <h2>유튜브 쿠키 설정</h2>
        <p className="cookie-modal-desc">
          유튜브 봇 감지 우회를 위해 브라우저의 유튜브 쿠키 전문(cookies.txt 형식)을 붙여넣어 주세요.<br/>
          (예: 'Get cookies.txt LOCALLY' 브라우저 확장 프로그램 사용)
        </p>
        
        {hasCookies && (
          <div className="cookie-status-active">
            ✅ 현재 저장된 쿠키가 있습니다. 새로 입력하면 덮어씁니다.
          </div>
        )}

        <textarea
          value={cookieContent}
          onChange={(e) => setCookieContent(e.target.value)}
          placeholder="# Netscape HTTP Cookie File..."
          className="cookie-textarea"
          rows={10}
        />
        
        {error && <div className="cookie-error">{error}</div>}
        
        <div className="cookie-modal-actions">
          {hasCookies && (
            <button className="cookie-btn-delete" onClick={handleDelete} disabled={loading}>
              저장된 쿠키 삭제
            </button>
          )}
          <button className="cookie-btn-cancel" onClick={onClose} disabled={loading}>취소</button>
          <button className="cookie-btn-save" onClick={handleSave} disabled={loading}>
            {loading ? '저장 중...' : '쿠키 저장'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CookieSettingsModal;
