import { NavLink } from 'react-router';
import { IconAccount } from '@/components/icons';
import { ROUTES } from '@/constants/routes';
import { useAuthStore } from '@/stores/useAuthStore';

/** Avatar de compte ancré à droite de la barre haute — mène directement au profil. */
export function OwnerAccountMenu() {
  const user = useAuthStore((s) => s.user);

  const initials =
    user && (user.prenom || user.nom)
      ? `${user.prenom?.[0] ?? ''}${user.nom?.[0] ?? ''}`.toUpperCase()
      : '';

  return (
    <NavLink
      to={ROUTES.PROFIL}
      className={({ isActive }) =>
        `flex items-center gap-2.5 rounded-full p-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:pr-3 ${
          isActive ? 'bg-secondary' : 'hover:bg-muted'
        }`
      }
    >
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-secondary text-[11px] font-bold text-primary">
        {initials || <IconAccount size={18} />}
      </span>
      <span className="hidden max-w-[140px] truncate text-[13.5px] font-semibold text-foreground sm:block">
        {user?.prenom ?? 'Mon compte'}
      </span>
    </NavLink>
  );
}
