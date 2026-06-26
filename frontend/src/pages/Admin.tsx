import { useState, useEffect } from 'react';
import type { User } from '@/context/AuthContext';
import { Check, X, Shield, ShieldOff } from 'lucide-react';
import api from '@/api';

export function Admin() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchUsers = async () => {
    try {
      const res = await api.get('/admin/users');
      setUsers(res.data);
    } catch (err: any) {
      setError('Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleUpdateStatus = async (userId: number, status: string) => {
    try {
      await api.put(`/admin/users/${userId}/status`, { status });
      await fetchUsers();
    } catch (err: any) {
      setError(`Failed to update user status: ${err.response?.data?.detail || 'Unknown error'}`);
    }
  };

  const handleUpdateRole = async (userId: number, role: string) => {
    try {
      await api.put(`/admin/users/${userId}/role`, { role });
      await fetchUsers();
    } catch (err: any) {
      setError(`Failed to update user role: ${err.response?.data?.detail || 'Unknown error'}`);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="sm:flex sm:items-center mb-8">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
          <p className="mt-2 text-sm text-gray-700">
            A list of all users including their role and current approval status.
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-md text-sm">
          {error}
        </div>
      )}

      <div className="mt-8 flex flex-col">
        <div className="-my-2 -mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
          <div className="inline-block min-w-full py-2 align-middle md:px-6 lg:px-8">
            <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
              <table className="min-w-full divide-y divide-gray-300 bg-white">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">ID</th>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">닉네임 / 이메일</th>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">인증</th>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Role</th>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Status</th>
                    <th className="relative py-3.5 pl-3 pr-4 sm:pr-6 text-right text-sm font-semibold text-gray-900">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">
                        {user.id}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        <div className="flex flex-col">
                          <span className="font-medium text-gray-900">
                            {user.nickname || '(미설정)'}
                          </span>
                          <span className="text-xs text-gray-400">{user.username}</span>
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          user.auth_provider === 'google'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}>
                          {user.auth_provider === 'google' ? '🔵 Google' : '🔑 Local'}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          user.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                          {user.role}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          user.status === 'approved'
                            ? 'bg-green-100 text-green-800'
                            : user.status === 'rejected'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-yellow-100 text-yellow-800'
                        }`}>
                          {user.status}
                        </span>
                      </td>
                      <td className="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                        <div className="flex justify-end gap-2">
                          {user.status !== 'approved' && (
                            <button
                              onClick={() => handleUpdateStatus(user.id, 'approved')}
                              className="text-green-600 hover:text-green-900 p-1 rounded-full hover:bg-green-50 transition-colors"
                              title="Approve User"
                            >
                              <Check className="h-5 w-5" />
                            </button>
                          )}
                          {user.status !== 'rejected' && (
                            <button
                              onClick={() => handleUpdateStatus(user.id, 'rejected')}
                              className="text-red-600 hover:text-red-900 p-1 rounded-full hover:bg-red-50 transition-colors"
                              title="Reject User"
                            >
                              <X className="h-5 w-5" />
                            </button>
                          )}
                          {user.role !== 'admin' ? (
                            <button
                              onClick={() => handleUpdateRole(user.id, 'admin')}
                              className="text-purple-600 hover:text-purple-900 p-1 rounded-full hover:bg-purple-50 transition-colors"
                              title="Make Admin"
                            >
                              <Shield className="h-5 w-5" />
                            </button>
                          ) : (
                            <button
                              onClick={() => handleUpdateRole(user.id, 'user')}
                              className="text-gray-600 hover:text-gray-900 p-1 rounded-full hover:bg-gray-50 transition-colors"
                              title="Remove Admin"
                            >
                              <ShieldOff className="h-5 w-5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-gray-500">
                        No users found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}