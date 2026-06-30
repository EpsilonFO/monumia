import { Link, Outlet } from 'react-router';
import { C } from '@/lib/brand';

export function BlogLayout() {
  return (
    <div className="min-h-screen" style={{ background: C.cream, color: C.ink }}>
      <header
        className="sticky top-0 z-30 border-b backdrop-blur"
        style={{ borderColor: C.border, background: 'rgba(255,254,251,0.82)' }}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3.5 sm:px-6 lg:px-8">
          <Link to="/blog" className="flex items-center gap-2.5">
            <img src="/monumia.png" alt="Monumia" className="h-8 w-8" />
            <span className="text-[18px] tracking-[-0.01em]" style={{ fontFamily: 'var(--font-serif)' }}>
              Monumia <span style={{ color: C.orange }}>Blog</span>
            </span>
          </Link>
          <Link
            to="/login"
            className="text-[13px] font-semibold hover:underline"
            style={{ color: C.blue }}
          >
            Accéder à l’application →
          </Link>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <Outlet />
      </main>
      <footer
        className="border-t py-8 text-center text-[12px]"
        style={{ borderColor: C.border, color: C.ink, opacity: 0.55 }}
      >
        © Monumia — Ressources pour les propriétaires et les communes
      </footer>
    </div>
  );
}
