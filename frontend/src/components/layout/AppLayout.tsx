import { useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useAideStore } from '@/stores/useAideStore';
import { useNotificationStore } from '@/stores/useNotificationStore';
import { monumentService } from '@/services/monument.service';
import { aideService } from '@/services/aide.service';
export function AppLayout() {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const setMonuments = useMonumentStore((s) => s.setMonuments);
  const setAides = useAideStore((s) => s.setAides);
  const getUnreadCount = useNotificationStore((s) => s.getUnreadCount);
  const navigate = useNavigate();

  useEffect(() => {
    if (!user) {
      navigate('/login');
    } else if (user.segment === 'btp') {
      navigate('/btp');
    }
  }, [user, navigate]);

  // Load monuments and aides when authenticated
  useEffect(() => {
    if (!token) return;
    monumentService.getAll().then(setMonuments).catch(console.error);
    aideService.getAll().then(setAides).catch(console.error);
  }, [token, setMonuments, setAides]);

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
