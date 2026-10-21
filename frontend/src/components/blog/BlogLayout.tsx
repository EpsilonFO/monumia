import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet, useLocation } from 'react-router';
import { C } from '@/lib/brand';
import { TopBar } from '@/components/layout/TopBar';
import { BottomNav } from '@/components/layout/BottomNav';

/**
 * Le blog reprend la barre horizontale de l'application (TopBar + BottomNav) afin
 * que l'onglet « Blog » reste mis en évidence et qu'on puisse revenir aux autres
 * espaces (tableau de bord, projets…). Le contenu garde l'habillage « crème » du blog.
 */
export function BlogLayout() {
  const { t } = useTranslation('blog');
  const mainRef = useRef<HTMLElement>(null);
  const { pathname } = useLocation();

  useEffect(() => {
    mainRef.current?.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div
      className="flex h-dvh flex-col overflow-hidden bg-app-bg"
      style={{ color: C.ink }}
    >
      <TopBar />
      <main ref={mainRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
          <Outlet />
        </div>
        <footer
          className="border-t py-8 text-center text-[14px]"
          style={{ borderColor: C.border, color: C.ink, opacity: 0.55 }}
        >
          {t('BlogLayout.piedDePage')}
        </footer>
      </main>
      <BottomNav />
    </div>
  );
}
