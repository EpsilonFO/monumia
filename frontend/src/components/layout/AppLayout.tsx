import { useEffect, useRef } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router';
import { TopBar } from './TopBar';
import { BottomNav } from './BottomNav';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useAideStore } from '@/stores/useAideStore';
import { monumentService } from '@/services/monument.service';
import { aideService } from '@/services/aide.service';

export function AppLayout() {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const setMonuments = useMonumentStore((s) => s.setMonuments);
  const setAides = useAideStore((s) => s.setAides);
  const navigate = useNavigate();

  useEffect(() => {
    if (!user) {
      navigate('/login');
    } else if (user.segment === 'btp') {
      navigate('/btp');
    }
  }, [user, navigate]);

  useEffect(() => {
    if (!token) return;
    monumentService.getAll().then(setMonuments).catch(console.error);
    aideService.getAll().then(setAides).catch(console.error);
  }, [token, setMonuments, setAides]);

  const mainRef = useRef<HTMLElement>(null);
  const { pathname } = useLocation();

  useEffect(() => {
    mainRef.current?.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-app-bg">
      <TopBar />
      <main ref={mainRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[1200px] px-4 pt-4 pb-8 md:px-6 md:py-6 lg:px-8">
          <Outlet />
        </div>
      </main>
      <BottomNav />
    </div>
  );
}
