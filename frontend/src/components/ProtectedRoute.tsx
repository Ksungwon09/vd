import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Loader2 } from 'lucide-react';

interface ProtectedRouteProps {
  children: ReactNode;
  requireAdmin?: boolean;
  requireApproved?: boolean;
}

export function ProtectedRoute({ children, requireAdmin, requireApproved }: ProtectedRouteProps) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900">
        <Loader2 className="h-8 w-8 animate-spin text-blue-400" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // 닉네임 미설정 → 닉네임 설정 페이지로 강제 이동
  if (user.needs_nickname) {
    return <Navigate to="/setup-nickname" replace />;
  }

  if (requireAdmin && user.role !== 'admin') {
    return <Navigate to="/" replace />;
  }

  if (requireApproved && user.status !== 'approved') {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}