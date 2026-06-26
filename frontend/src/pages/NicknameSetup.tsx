import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { UserCircle, ShieldCheck, Loader2 } from 'lucide-react';
import api from '@/api';

/**
 * 최초 Google 로그인 후 닉네임을 설정하는 페이지.
 * - 닉네임이 'admin'이고 아직 관리자가 없으면 → 관리자 역할 자동 부여
 * - 설정 완료 후 홈으로 이동
 */
export function NicknameSetup() {
  const [nickname, setNickname] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);
  const { refreshUser }         = useAuth();
  const navigate                = useNavigate();

  const isAdmin = nickname.trim().toLowerCase() === 'admin';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!nickname.trim()) {
      setError('닉네임을 입력해주세요.');
      return;
    }
    setLoading(true);
    try {
      await api.post('/auth/setup-nickname', { nickname: nickname.trim() });
      await refreshUser();
      navigate('/', { replace: true });
    } catch (err: any) {
      setError(err.response?.data?.detail || '닉네임 설정에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900
                    flex flex-col justify-center items-center px-4">
      {/* 배경 블러 효과 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/3 left-1/3 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/3 right-1/3 w-72 h-72 bg-indigo-500/10 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-md">
        {/* 헤더 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl
                          bg-blue-600/20 border border-blue-500/30 backdrop-blur-sm mb-6
                          shadow-lg shadow-blue-500/20">
            <UserCircle className="h-10 w-10 text-blue-400" />
          </div>
          <h1 className="text-3xl font-bold text-white">닉네임 설정</h1>
          <p className="mt-2 text-slate-400 text-sm">
            서비스에서 사용할 닉네임을 입력해주세요
          </p>
        </div>

        {/* 카드 */}
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                닉네임
              </label>
              <input
                id="nickname-input"
                type="text"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                placeholder="2~20자 입력"
                maxLength={20}
                autoFocus
                className="w-full px-4 py-3 rounded-xl bg-white/10 border border-white/20
                           text-white placeholder-slate-500 text-sm
                           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                           transition-all duration-200"
              />

              {/* admin 닉네임 미리보기 */}
              {isAdmin && (
                <div className="mt-3 flex items-center gap-2 text-amber-400 text-xs
                                bg-amber-400/10 border border-amber-400/20 rounded-lg px-3 py-2">
                  <ShieldCheck className="w-4 h-4 flex-shrink-0" />
                  <span>관리자 권한이 부여됩니다 (최초 1명만 가능)</span>
                </div>
              )}
            </div>

            {error && (
              <div className="flex items-start gap-2 text-red-400 text-sm
                              bg-red-400/10 border border-red-400/20 rounded-xl px-4 py-3">
                <span>⚠️</span>
                <span>{error}</span>
              </div>
            )}

            <button
              id="submit-nickname-btn"
              type="submit"
              disabled={loading || !nickname.trim()}
              className="w-full flex items-center justify-center gap-2
                         px-6 py-3.5 rounded-xl font-semibold text-sm
                         bg-blue-600 hover:bg-blue-500 text-white
                         disabled:opacity-50 disabled:cursor-not-allowed
                         active:scale-[0.98] transition-all duration-200
                         shadow-lg shadow-blue-600/30"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {loading ? '설정 중...' : '닉네임 설정 완료'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
