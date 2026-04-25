import { NavLink, useNavigate } from 'react-router';
import {
  LayoutDashboard,
  Church,
  FolderOpen,
  FileStack,
  User,
  LogOut,
} from 'lucide-react';
import { useAuthStore } from '@/stores/useAuthStore';

const navItems = [
  { to: '/app', icon: LayoutDashboard, label: 'Tableau de bord' },
  { to: '/app/monuments', icon: Church, label: 'Monuments' },
  { to: '/app/dossiers', icon: FolderOpen, label: 'Dossiers' },
  { to: '/app/documents', icon: FileStack, label: 'Documents' },
  { to: '/app/profil', icon: User, label: 'Profil' },
];

export function Sidebar() {
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const segmentLabel = user?.segment === 'commune'
    ? 'Commune'
    : user?.segment === 'prive'
      ? 'Propriétaire'
      : 'Patrimoine';

  return (
    <aside className="hidden md:flex md:flex-col md:w-[220px] shrink-0 bg-[#F2F0EB] border-r border-[#E0DDD6]">
      {/* Logo block */}
      <div className="px-5 pt-5 pb-4">
        <a href="/" className="flex items-center gap-2.5">
          <img src="/patrialta.png" alt="PatriAlta" className="h-8 w-8" />
          <div>
            <span
              className="text-[17px] font-normal tracking-[-0.01em] text-[#1B1E2E]"
              style={{ fontFamily: "'Cormorant Garamond', serif" }}
            >
              PatriAlta
            </span>
            <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#C75B3A]">{segmentLabel}</div>
          </div>
        </a>
      </div>

      {/* Decorative rule */}
      <div className="mx-5 h-px bg-gradient-to-r from-[#C75B3A]/30 via-[#E0DDD6] to-transparent" />

      {/* User */}
      {user && (
        <div className="px-5 py-3">
          <p className="text-[13px] font-semibold text-[#1B1E2E] truncate">
            {user.prenom} {user.nom}
          </p>
          <p className="text-[11px] text-[#8E92A4] truncate">{user.email}</p>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 space-y-0.5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/app'}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-white text-[#1A237E] shadow-[0_1px_3px_rgba(0,0,0,0.04)]'
                  : 'text-[#5C6178] hover:bg-white/60 hover:text-[#1B1E2E]'
              }`
            }
          >
            <item.icon className="h-[15px] w-[15px]" strokeWidth={1.8} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-[#E0DDD6]">
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 w-full px-2 py-1 text-[11px] font-medium text-[#8E92A4] rounded transition-colors duration-200 hover:text-[#5C6178]"
        >
          <LogOut className="h-3 w-3" strokeWidth={1.8} />
          Déconnexion
        </button>
      </div>
    </aside>
  );
}
