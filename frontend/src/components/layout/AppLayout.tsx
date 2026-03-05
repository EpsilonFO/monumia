import { useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useAuthStore } from '@/stores/useAuthStore';
import { useNotificationStore } from '@/stores/useNotificationStore';
import { mockUsers } from '@/data/mock-users';

export function AppLayout() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const getUnreadCount = useNotificationStore((s) => s.getUnreadCount);
  const navigate = useNavigate();

  useEffect(() => {
    if (!user) {
      setUser(mockUsers[0]);
    } else if (user.segment === 'btp') {
      navigate('/btp');
    }
  }, [user, setUser, navigate]);

  const unreadCount = user ? getUnreadCount(user.id) : 0;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar unreadCount={unreadCount} />
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
