import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { LogOut, Download, ShieldCheck, Settings } from 'lucide-react';
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

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  if (!user) return null;

  return (
    <>
      <nav className="bg-white shadow-sm border-b relative z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <Link to="/" className="flex flex-shrink-0 items-center text-xl font-bold text-blue-600 gap-2">
                <Download className="h-6 w-6" />
                Private V-Downloader
              </Link>
            </div>
            <div className="flex items-center gap-4">
              {user.role === 'admin' && (
                <Link to="/admin" className="text-gray-600 hover:text-blue-600 flex items-center gap-1 font-medium text-sm">
                  <ShieldCheck className="h-4 w-4" />
                  Admin
                </Link>
              )}
              <span className="text-sm text-gray-500">
                Welcome, <span className="font-semibold text-gray-700">{user.username}</span>
              </span>
              <button
                onClick={() => setIsCookieModalOpen(true)}
                className="text-gray-500 hover:text-blue-600 p-2 rounded-full hover:bg-gray-100 transition-colors"
                title="Settings"
              >
                <Settings className="h-5 w-5" />
              </button>
              <button
                onClick={handleLogout}
                className="text-gray-500 hover:text-red-600 p-2 rounded-full hover:bg-gray-100 transition-colors"
                title="Logout"
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