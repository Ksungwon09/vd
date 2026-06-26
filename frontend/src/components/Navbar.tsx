import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { LogOut, Download, ShieldCheck, Settings, User } from 'lucide-react';
import { useState, useEffect } from 'react';
import CookieSettingsModal from './CookieSettingsModal';

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isCookieModalOpen, setIsCookieModalOpen] = useState(false);

  useEffect(() => {
    const handleOpen = () => setIsCookieModalOpen(true);
    window.addEventListener('open-cookie-modal', handleOpen);
    return () => window.removeEventListener('open-cookie-modal', handleOpen);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  if (!user) return null;

  // 표시 이름: 닉네임 우선, 없으면 이메일 앞부분
  const displayName = user.nickname || user.username?.split('@')[0] || '사용자';

  return (
    <>
      <nav className="bg-white shadow-sm border-b relative z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            {/* 로고 */}
            <div className="flex">
              <Link
                to="/"
                className="flex flex-shrink-0 items-center text-xl font-bold text-blue-600 gap-2"
              >
                <Download className="h-6 w-6" />
                Private V-Downloader
              </Link>
            </div>

            {/* 우측 메뉴 */}
            <div className="flex items-center gap-4">
              {user.role === 'admin' && (
                <Link
                  to="/admin"
                  className="text-gray-600 hover:text-blue-600 flex items-center gap-1 font-medium text-sm"
                >
                  <ShieldCheck className="h-4 w-4" />
                  Admin
                </Link>
              )}

              {/* 유저 정보 */}
              <div className="flex items-center gap-1.5 text-sm text-gray-500">
                <User className="h-4 w-4" />
                <span>
                  Welcome,{' '}
                  <span className="font-semibold text-gray-700">{displayName}</span>
                  {user.role === 'admin' && (
                    <span className="ml-1.5 text-xs font-medium text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-full border border-amber-200">
                      관리자
                    </span>
                  )}
                </span>
              </div>

              {/* 쿠키/인증 설정 */}
              <button
                onClick={() => setIsCookieModalOpen(true)}
                className="text-gray-500 hover:text-blue-600 p-2 rounded-full hover:bg-gray-100 transition-colors"
                title="인증 설정"
              >
                <Settings className="h-5 w-5" />
              </button>

              {/* 로그아웃 */}
              <button
                id="logout-btn"
                onClick={handleLogout}
                className="text-gray-500 hover:text-red-600 p-2 rounded-full hover:bg-gray-100 transition-colors"
                title="로그아웃"
              >
                <LogOut className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      </nav>

      <CookieSettingsModal
        isOpen={isCookieModalOpen}
        onClose={() => setIsCookieModalOpen(false)}
        onSaveSuccess={() => {}}
      />
    </>
  );
}