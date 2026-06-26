import { Download } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

export function Login() {
  const { loginWithGoogle } = useAuth();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex flex-col justify-center items-center px-4">
      {/* 배경 효과 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl animate-pulse delay-1000" />
      </div>

      <div className="relative z-10 w-full max-w-md">
        {/* 로고 */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-blue-600/20 border border-blue-500/30 backdrop-blur-sm mb-6 shadow-lg shadow-blue-500/20">
            <Download className="h-10 w-10 text-blue-400" />
          </div>
          <h1 className="text-4xl font-bold text-white tracking-tight">
            V-Downloader
          </h1>
          <p className="mt-2 text-slate-400 text-sm">
            프라이빗 영상 다운로드 서비스
          </p>
        </div>

        {/* 카드 */}
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl">
          <h2 className="text-xl font-semibold text-white text-center mb-2">
            로그인
          </h2>
          <p className="text-slate-400 text-sm text-center mb-8">
            Google 계정으로 안전하게 시작하세요
          </p>

          <button
            id="google-login-btn"
            onClick={loginWithGoogle}
            className="w-full flex items-center justify-center gap-3 px-6 py-3.5 rounded-xl
                       bg-white text-gray-700 font-semibold text-sm
                       hover:bg-gray-50 active:scale-[0.98]
                       transition-all duration-200 shadow-lg
                       border border-gray-200 group"
          >
            {/* Google 로고 (SVG) */}
            <svg viewBox="0 0 24 24" className="w-5 h-5 flex-shrink-0">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
            <span>Google 계정으로 로그인</span>
          </button>

          <p className="mt-6 text-center text-xs text-slate-500">
            로그인하면 이용약관 및 개인정보처리방침에 동의하는 것으로 간주됩니다.
          </p>
        </div>
      </div>
    </div>
  );
}