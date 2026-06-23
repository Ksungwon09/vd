import { Clock } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { useNavigate } from 'react-router-dom';

export function Pending() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="flex justify-center text-yellow-500 mb-6">
          <Clock className="h-16 w-16" />
        </div>
        <h2 className="text-3xl font-extrabold text-gray-900 mb-4">
          Approval Pending
        </h2>
        <p className="text-lg text-gray-600 mb-8">
          Your account has been created successfully, but you are waiting for an administrator to approve your access.
        </p>
        <button
          onClick={handleLogout}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-blue-700 bg-blue-100 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}