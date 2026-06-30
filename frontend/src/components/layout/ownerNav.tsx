import type { ComponentType } from 'react';
import { NavLink, useNavigate } from 'react-router';
import { ChevronDown } from 'lucide-react';
import { IconDashboard, IconMonument, IconDocuments, IconHelp, IconAccount, IconDeconnexion } from '@/components/icons';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { C } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { useAuthStore } from '@/stores/useAuthStore';

export interface NavItem {
  to: string;
  icon: ComponentType<{ size?: number; className?: string }>;
  label: string;
  end?: boolean;
}

/** Navigation principale du propriétaire — peu d'entrées, présentées en barre haute. */
export const ownerNavItems: NavItem[] = [
  { to: ROUTES.DASHBOARD, icon: IconDashboard, label: 'Tableau de bord', end: true },
  { to: ROUTES.PROJETS, icon: IconMonument, label: 'Mes projets' },
  { to: ROUTES.DOCUMENTS, icon: IconDocuments, label: 'Mes documents' },
];

function segmentTagline(segment?: string): string {
  if (segment === 'commune') return 'Commune';
  if (segment === 'prive') return 'Propriétaire';
  return 'Patrimoine';
}

export function useOwnerBrand() {
  const user = useAuthStore((s) => s.user);
  return { tagline: segmentTagline(user?.segment) };
}

/** Menu de compte (avatar + déroulant) ancré à droite de la barre haute. */
export function OwnerAccountMenu() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const initials =
    user && (user.prenom || user.nom)
      ? `${user.prenom?.[0] ?? ''}${user.nom?.[0] ?? ''}`.toUpperCase()
      : '';

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-2 rounded-full p-1 pr-1 transition-colors hover:bg-[var(--secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:pr-2.5"
        >
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold"
            style={{ background: C.paleBlue, color: C.blue }}
          >
            {initials || <IconAccount size={18} />}
          </span>
          <span
            className="hidden max-w-[120px] truncate text-[13.5px] font-medium sm:block"
            style={{ color: C.ink }}
          >
            {user?.prenom ?? 'Mon compte'}
          </span>
          <ChevronDown className="hidden h-4 w-4 shrink-0 sm:block" style={{ color: C.grayMuted }} />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" sideOffset={8} className="w-60">
        <div className="px-2 py-1.5">
          <p className="truncate text-[13px] font-semibold" style={{ color: C.ink }}>
            {user ? `${user.prenom} ${user.nom}` : 'Mon compte'}
          </p>
          {user?.email && (
            <p className="truncate text-[11.5px]" style={{ color: C.grayMuted }}>
              {user.email}
            </p>
          )}
        </div>

        <DropdownMenuSeparator />

        <DropdownMenuItem asChild>
          <NavLink to={ROUTES.PROFIL} className="cursor-pointer">
            <IconAccount size={16} />
            Mon compte
          </NavLink>
        </DropdownMenuItem>

        <DropdownMenuItem asChild>
          <a href="mailto:contact@monumia.fr" className="cursor-pointer">
            <IconHelp size={16} />
            Aide &amp; contact
          </a>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <DropdownMenuItem variant="destructive" onSelect={handleLogout} className="cursor-pointer">
          <IconDeconnexion className="h-4 w-4" />
          Déconnexion
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
