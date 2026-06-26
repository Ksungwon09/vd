import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import api, { setAccessToken, getAccessToken } from '@/api';

export interface User {
  id: number;
  username: string | null;
  nickname: string | null;
  role: string;
  status: string;
  auth_provider: string;
  needs_nickname: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  loginWithGoogle: () => void;
  logout: () => Promise<void>;
  /** OAuthCallback 페이지에서 콜백 수신 후 호출 */
  handleAuthCallback: (token: string) => Promise<User>;
  /** 닉네임 설정 완료 후 유저 정보 갱신 */
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]       = useState<User | null>(null);
  const [token, setToken]     = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  /** /auth/me를 호출하여 유저 정보를 갱신합니다. */
  const fetchUser = useCallback(async (): Promise<User | null> => {
    try {
      const res = await api.get<User>('/auth/me');
      setUser(res.data);
      return res.data;
    } catch {
      setUser(null);
      setToken(null);
      setAccessToken(null);
      return null;
    }
  }, []);

  /** 페이지 로드 시 refresh_token 쿠키로 access_token 복원 시도 */
  useEffect(() => {
    const init = async () => {
      try {
        const res = await api.post<{ access_token: string }>('/auth/refresh');
        const newToken = res.data.access_token;
        setAccessToken(newToken);
        setToken(newToken);
        await fetchUser();
      } catch {
        // refresh_token이 없거나 만료 → 로그아웃 상태
        setUser(null);
        setToken(null);
        setAccessToken(null);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [fetchUser]);

  /** Google OAuth2 로그인 시작 — 브라우저를 백엔드 로그인 URL로 이동 */
  const loginWithGoogle = () => {
    window.location.href = '/api/auth/google/login';
  };

  /** OAuthCallback 페이지에서 URL 파라미터로 받은 token을 처리 */
  const handleAuthCallback = async (newToken: string): Promise<User> => {
    setAccessToken(newToken);
    setToken(newToken);
    const fetchedUser = await fetchUser();
    if (!fetchedUser) throw new Error('유저 정보를 가져올 수 없습니다.');
    return fetchedUser;
  };

  /** 닉네임 설정 등 변경 사항 반영 */
  const refreshUser = async () => {
    await fetchUser();
  };

  /** 로그아웃: 쿠키 삭제 + 상태 초기화 */
  const logout = async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      // 서버 오류여도 클라이언트 상태는 초기화
    }
    setAccessToken(null);
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, token, loading, loginWithGoogle, logout, handleAuthCallback, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}