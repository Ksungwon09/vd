import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Loader2 } from 'lucide-react';

/**
 * Google OAuth2 콜백 처리 페이지
 * 백엔드가 리다이렉트한 URL: /auth/callback?token=XXX&needs_nickname=1
 *
 * 역할:
 *  1. URL 파라미터에서 access_token 추출
 *  2. AuthContext에 저장
 *  3. needs_nickname 여부에 따라 /setup-nickname 또는 / 로 이동
 */
export function OAuthCallback() {
  const [searchParams] = useSearchParams();
  const { handleAuthCallback } = useAuth();
  const navigate = useNavigate();
  const processed = useRef(false); // StrictMode 이중 실행 방지

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const token        = searchParams.get('token');
    const needsNickname = searchParams.get('needs_nickname') === '1';

    if (!token) {
      navigate('/login', { replace: true });
      return;
    }

    handleAuthCallback(token)
      .then(() => {
        // URL에서 token 파라미터 제거 후 이동
        if (needsNickname) {
          navigate('/setup-nickname', { replace: true });
        } else {
          navigate('/', { replace: true });
        }
      })
      .catch(() => {
        navigate('/login', { replace: true });
      });
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900
                    flex flex-col items-center justify-center gap-4 text-white">
      <Loader2 className="w-10 h-10 animate-spin text-blue-400" />
      <p className="text-slate-300 text-sm">Google 계정으로 로그인 중...</p>
    </div>
  );
}
