import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Navbar } from './components/Navbar';
import { Login } from './pages/Login';
import { Admin } from './pages/Admin';
import { Home } from './pages/Home';
import { OAuthCallback } from './pages/OAuthCallback';
import { NicknameSetup } from './pages/NicknameSetup';

function AppContent() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Routes>
        {/* 인증 없이 접근 가능한 페이지 */}
        <Route path="/login"          element={<Login />} />
        <Route path="/auth/callback"  element={<OAuthCallback />} />
        <Route path="/setup-nickname" element={<NicknameSetup />} />

        {/* 인증 필요 + Navbar 포함 */}
        <Route
          path="/*"
          element={
            <>
              <Navbar />
              <main className="flex-grow">
                <Routes>
                  <Route
                    path="/admin"
                    element={
                      <ProtectedRoute requireAdmin requireApproved>
                        <Admin />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/"
                    element={
                      <ProtectedRoute requireApproved>
                        <Home />
                      </ProtectedRoute>
                    }
                  />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </main>
            </>
          }
        />
      </Routes>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppContent />
      </Router>
    </AuthProvider>
  );
}

export default App;