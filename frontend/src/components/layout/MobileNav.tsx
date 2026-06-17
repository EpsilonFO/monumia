import { NavLink } from 'react-router';
import { LayoutDashboard, Landmark, FileStack, User } from 'lucide-react';
import { C, SERIF } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { landingUrl } from '@/lib/session';

const navItems = [
  { to: ROUTES.DASHBOARD, icon: LayoutDashboard, label: 'Tableau de bord' },
  { to: ROUTES.PROJETS, icon: Landmark, label: 'Projets' },
  { to: ROUTES.DOCUMENTS, icon: FileStack, label: 'Documents' },
  { to: ROUTES.PROFIL, icon: User, label: 'Profil' },
];

interface MobileNavProps {
  onNavigate?: () => void;
}

export function MobileNav({ onNavigate }: MobileNavProps) {
  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: C.blue }}>
      <a
        href={landingUrl()}
        className="flex items-center gap-2.5 px-5 py-4"
        style={{ borderBottom: `1px solid ${C.blueDark}` }}
      >
        <img src="/monumia.png" alt="Monumia" className="h-7 w-7" />
        <span
          className="text-[16px] font-bold tracking-[-0.01em]"
          style={{ fontFamily: SERIF, color: C.cream }}
        >
          Monumia
        </span>
      </a>

      <nav className="flex-1 px-3 py-3 space-y-0.5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === ROUTES.DASHBOARD}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-200 ${
                isActive ? 'text-white' : 'hover:bg-white/10'
              }`
            }
            style={({ isActive }) => ({
              backgroundColor: isActive ? C.orange : 'transparent',
              color: isActive ? '#ffffff' : C.paleBlue,
            })}
          >
            <item.icon className="h-[15px] w-[15px]" strokeWidth={1.8} />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
