import { NavLink, useNavigate } from 'react-router';
import { IconDashboard, IconMonument, IconDocuments, IconHelp, IconAccount } from '@/components/icons';
import { LogOut } from 'lucide-react';
import type { SidebarSection } from './SidebarNav';
import { C } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { useAuthStore } from '@/stores/useAuthStore';

export const ownerSections: SidebarSection[] = [
  {
    title: 'Pilotage',
    items: [
      { to: ROUTES.DASHBOARD, icon: IconDashboard, label: 'Tableau de bord', end: true },
      { to: ROUTES.PROJETS, icon: IconMonument, label: 'Mes projets' },
    ],
  },
  {
    title: 'Documents',
    items: [{ to: ROUTES.DOCUMENTS, icon: IconDocuments, label: 'Mes documents' }],
  },
];

export function OwnerAccount({ onNavigate }: { onNavigate?: () => void }) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="space-y-1">
      <a
        href="mailto:contact@monumia.fr"
        onClick={onNavigate}
        className="flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-colors hover:bg-[var(--color-secondary)]"
        style={{ color: C.grayFg }}
      >
        <IconHelp size={20} className="shrink-0" />
        Aide &amp; contact
      </a>

      <NavLink
        to={ROUTES.PROFIL}
        onClick={onNavigate}
        className="flex items-center gap-3 rounded-xl px-3 py-2 transition-colors hover:bg-[var(--color-secondary)]"
      >
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
          style={{ background: C.paleBlue, color: C.blue }}
        >
          <IconAccount size={18} />
        </span>
        <span className="min-w-0 flex-1 leading-tight">
          <span className="block truncate text-[13px] font-semibold" style={{ color: C.ink }}>
            {user ? `${user.prenom} ${user.nom}` : 'Mon compte'}
          </span>
          <span className="block truncate text-[11px]" style={{ color: C.grayMuted }}>
            {user?.email ?? 'Profil'}
          </span>
        </span>
      </NavLink>

      <button
        onClick={handleLogout}
        className="flex min-h-11 w-full items-center gap-2 rounded-xl px-3 py-2 text-[12px] font-medium transition-colors hover:bg-[var(--color-secondary)]"
        style={{ color: C.grayMuted }}
      >
        <LogOut className="h-3.5 w-3.5" strokeWidth={1.8} />
        Déconnexion
      </button>
    </div>
  );
}

function segmentTagline(segment?: string): string {
  if (segment === 'commune') return 'Commune';
  if (segment === 'prive') return 'Propriétaire';
  return 'Patrimoine';
}

export function useOwnerBrand() {
  const user = useAuthStore((s) => s.user);
  return { tagline: segmentTagline(user?.segment) };
}
