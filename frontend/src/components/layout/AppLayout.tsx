import { useEffect, useRef } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router';
import { TopBar } from './TopBar';
import { BottomNav } from './BottomNav';
import { BienvenueBeta } from '@/components/shared/BienvenueBeta';
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

  // `h-dvh` et non `h-screen` : sur Safari iPhone, `100vh` compte la place de
  // la barre d'outils du navigateur. Le cadre dépassait de 40 px (754 pour 714
  // visibles), la barre du bas passait dessous et toute la page bougeait.
  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-background">
      <TopBar />
      {/* `scrollbar-gutter: stable` : la place de la barre de défilement est
          toujours réservée. Sans elle, passer d'un onglet court (fiche) à un
          onglet long (projets, documents) la faisait apparaître, et toute la
          colonne centrée sautait de sa largeur vers la gauche. */}
      <main ref={mainRef} className="flex-1 overflow-y-auto [scrollbar-gutter:stable]">
        {/* La largeur des maquettes d'écran (1180 px), agrandie par les deux zooms du 2026-09-30. */}
        <div className="mx-auto w-[min(1343.5px,100%-36.5px)] pt-[18px] pb-[90px] md:pt-[26px]">
          <Outlet />
        </div>
      </main>
      <BottomNav />
      {/* Accueil des bêta-testeurs, une fois par compte : ne rend rien sans VITE_YBUG_ID. */}
      <BienvenueBeta />
    </div>
  );
}
