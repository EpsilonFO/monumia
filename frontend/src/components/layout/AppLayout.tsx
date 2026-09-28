import { useEffect, useRef } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router';
import { TopBar } from './TopBar';
import { BottomNav } from './BottomNav';
import { useAuthStore } from '@/stores/useAuthStore';
import { useBillingStore } from '@/stores/useBillingStore';
import { dashboardService } from '@/services/dashboard.service';
import '@/components/shared/ecrans/ecrans.css';

export function AppLayout() {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const loadAccess = useBillingStore((s) => s.loadAccess);
  const navigate = useNavigate();

  useEffect(() => {
    if (!user) {
      navigate('/login');
    }
  }, [user, navigate]);

  // Monuments, projets, dossiers, digests et suivis : toutes les pages de cet
  // espace en ont besoin, et `GET /dashboard` les sert en un seul appel. C'est
  // la source unique — un `GET /monuments` en parallèle refaisait tout le
  // travail de `fetch_user_monuments` côté serveur, et les deux réponses se
  // couraient après dans le store. Les pages qui l'appellent aussi à leur
  // montage rejoignent la requête en vol (cf. dashboardService.load).
  useEffect(() => {
    if (!token) return;
    dashboardService.load().catch(console.error);
  }, [token]);

  // Droits de facturation : quels projets sont débloqués. Non persistés, donc
  // rechargés à chaque ouverture de session.
  useEffect(() => {
    if (!token) return;
    loadAccess();
  }, [token, loadAccess]);

  const mainRef = useRef<HTMLElement>(null);
  const { pathname } = useLocation();

  useEffect(() => {
    mainRef.current?.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      <TopBar />
      <main ref={mainRef} className="flex-1 overflow-y-auto">
        {/* La largeur des maquettes d'écran : 1180 px, 16 px de marge en deçà. */}
        <div className="mx-auto w-[min(1180px,100%-32px)] pt-[23px] pb-[79px]">
          <Outlet />
        </div>
      </main>
      <BottomNav />
    </div>
  );
}
