import { NavLink, useNavigate } from 'react-router';
import { Gauge, Users, HandCoins, Archive, LogOut } from 'lucide-react';
import { IconAccount } from '@/components/icons';
import { SidebarNav } from './SidebarNav';
import type { SidebarSection } from './SidebarNav';
import { C } from '@/lib/brand';
import { useAuthStore } from '@/stores/useAuthStore';
import { landingUrl } from '@/lib/session';

const btpSections: SidebarSection[] = [
  {
    title: 'Pilotage',
    items: [
      { to: '/btp', icon: Gauge, label: 'Tableau de bord', end: true },
      { to: '/btp/prospects', icon: Users, label: 'Prospects' },
    ],
  },
  {
    title: 'Outils',
    items: [
      { to: '/btp/aides', icon: HandCoins, label: 'Catalogue aides' },
      { to: '/btp/documents', icon: Archive, label: 'Documents' },
    ],
  },
];

function BtpAccount({ onNavigate }: { onNavigate?: () => void }) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const handleLogout = () => {
    logout();
    navigate('/login');
  };
  return (
    <div className="space-y-1">
      <NavLink
        to="/btp/profil"
        onClick={onNavigate}
        className="flex items-center gap-3 rounded-xl px-3 py-2 transition-colors hover:bg-[var(--color-secondary)]"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full" style={{ background: C.paleBlue, color: C.blue }}>
          <IconAccount size={18} />
        </span>
        <span className="min-w-0 flex-1 leading-tight">
          <span className="block truncate text-[13px] font-semibold" style={{ color: C.ink }}>
            {user?.btp?.raisonSociale ?? 'Mon entreprise'}
          </span>
          <span className="block truncate text-[11px]" style={{ color: C.grayMuted }}>
            {user ? `${user.prenom} ${user.nom}` : 'Mon profil'}
          </span>
        </span>
      </NavLink>
      <button
        onClick={handleLogout}
        className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-[12px] font-medium transition-colors hover:bg-[var(--color-secondary)]"
        style={{ color: C.grayMuted }}
      >
        <LogOut className="h-3.5 w-3.5" strokeWidth={1.8} />
        Changer de profil
      </button>
    </div>
  );
}

export function BtpSidebar({ onNavigate }: { onNavigate?: () => void } = {}) {
  return (
    <aside
      className="hidden shrink-0 md:flex md:w-[240px] md:flex-col"
      style={{ borderRight: '1px solid var(--color-border)' }}
    >
      <SidebarNav
        brand={{ name: 'Monumia', tagline: 'Espace BTP', href: landingUrl() }}
        sections={btpSections}
        account={<BtpAccount onNavigate={onNavigate} />}
        onNavigate={onNavigate}
      />
    </aside>
  );
}
