import { NavLink, useNavigate } from 'react-router';
import { LayoutDashboard, Landmark, FileStack, LayoutTemplate, User, LogOut } from 'lucide-react';
import { useAuthStore } from '@/stores/useAuthStore';
import { C, SERIF } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { landingUrl } from '@/lib/session';

const navItems = [
  { to: ROUTES.DASHBOARD, icon: LayoutDashboard, label: 'Tableau de bord' },
  { to: ROUTES.PROJETS, icon: Landmark, label: 'Projets' },
  { to: ROUTES.DOCUMENTS, icon: FileStack, label: 'Mes documents' },
  { to: ROUTES.MODELES, icon: LayoutTemplate, label: 'Modèles' },
  { to: ROUTES.PROFIL, icon: User, label: 'Profil' },
];

export function Sidebar() {
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const segmentLabel =
    user?.segment === 'commune'
      ? 'Commune'
      : user?.segment === 'prive'
        ? 'Propriétaire'
        : 'Patrimoine';

  return (
    <aside
      className="hidden md:flex md:flex-col md:w-[220px] shrink-0"
      style={{ backgroundColor: C.blue, borderRight: '1px solid #0e3f9a' }}
    >
      {/* Logo block */}
      <div className="px-5 pt-5 pb-4">
        <a href={landingUrl()} className="flex items-center gap-2.5">
          <img src="/monumia.png" alt="Monumia" className="h-8 w-8" />
          <div>
            <span
              className="text-[18px] font-bold tracking-[-0.01em]"
              style={{ fontFamily: SERIF, color: C.cream }}
            >
              Monumia
            </span>
            <div
              className="text-[10px] font-bold uppercase tracking-[0.15em]"
              style={{ color: C.orange }}
            >
              {segmentLabel}
            </div>
          </div>
        </a>
      </div>

      {/* Decorative rule */}
      <div
        className="mx-5 h-px"
        style={{
          background: `linear-gradient(to right, ${C.orange}66, ${C.blueDark}, transparent)`,
        }}
      />

      {/* User */}
      {user && (
        <div className="px-5 py-3">
          <p className="text-[13px] font-semibold truncate" style={{ color: C.cream }}>
            {user.prenom} {user.nom}
          </p>
          <p className="text-[11px] truncate" style={{ color: C.blueLight }}>
            {user.email}
          </p>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 space-y-0.5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === ROUTES.DASHBOARD}
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

      {/* Footer */}
      <div className="px-4 py-3" style={{ borderTop: `1px solid ${C.blueDark}` }}>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 w-full px-2 py-1 text-[11px] font-medium rounded transition-colors duration-200 hover:text-white"
          style={{ color: C.blueLight }}
        >
          <LogOut className="h-3 w-3" strokeWidth={1.8} />
          Déconnexion
        </button>
      </div>
    </aside>
  );
}
