import { NavLink } from 'react-router';
import { IconAccount } from '@/components/icons';
import { C } from '@/lib/brand';
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
        `flex items-center gap-2 rounded-full p-1 pr-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:pr-2.5 ${
          isActive ? 'bg-[var(--secondary)]' : 'hover:bg-[var(--secondary)]'
        }`
      }
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
    </NavLink>
  );
}
