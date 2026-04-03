import { Outlet, useNavigate } from 'react-router';

const C = {
  bg: '#F8F7F4',
  text: '#1B1E2E',
  textLight: '#8E92A4',
  border: '#E4E2DC',
  terra: '#C75B3A',
} as const;

export function OnboardingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex flex-col" style={{ background: C.bg, color: C.text }}>
      {/* header */}
      <header className="flex items-center justify-between px-6 lg:px-10 py-5" style={{ borderBottom: `1px solid ${C.border}` }}>
        <button onClick={() => navigate('/')} className="flex items-center gap-3 group">
          <img src="/patrialta.png" alt="PatriAlta" className="h-7 object-contain" />
          <span className="text-[15px] font-semibold tracking-wide" style={{ color: C.text }}>PatriAlta</span>
        </button>
        <span className="text-[12px] font-semibold uppercase tracking-[0.15em]" style={{ color: C.terra }}>
          Inscription
        </span>
      </header>

      {/* content */}
      <main className="flex-1 flex items-center justify-center px-6 py-6">
        <div className="w-full max-w-2xl">
          <Outlet />
        </div>
      </main>

      {/* subtle footer */}
      <footer className="py-4 text-center">
        <p className="text-[11px] uppercase tracking-[0.12em]" style={{ color: C.textLight }}>
          © {new Date().getFullYear()} PatriAlta
        </p>
      </footer>
    </div>
  );
}
