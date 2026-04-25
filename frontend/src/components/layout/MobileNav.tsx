import { NavLink } from 'react-router';
import {
  LayoutDashboard,
  Church,
  HandCoins,
  FolderOpen,
  FileStack,
  User,
} from 'lucide-react';

const navItems = [
  { to: '/app', icon: LayoutDashboard, label: 'Tableau de bord' },
  { to: '/app/monuments', icon: Church, label: 'Monuments' },
  { to: '/app/aides', icon: HandCoins, label: 'Aides' },
  { to: '/app/dossiers', icon: FolderOpen, label: 'Dossiers' },
  { to: '/app/documents', icon: FileStack, label: 'Documents' },
  { to: '/app/profil', icon: User, label: 'Profil' },
];

interface MobileNavProps {
  onNavigate?: () => void;
}

export function MobileNav({ onNavigate }: MobileNavProps) {
  return (
    <div className="flex flex-col h-full bg-[#F2F0EB]">
      <div className="flex items-center gap-2.5 px-5 py-4 border-b border-[#E0DDD6]">
        <img src="/patrialta.png" alt="PatriAlta" className="h-7 w-7" />
        <span
          className="text-[15px] font-normal tracking-[-0.01em] text-[#1B1E2E]"
          style={{ fontFamily: "'Cormorant Garamond', serif" }}
        >
          PatriAlta
        </span>
      </div>

      <nav className="flex-1 px-3 py-3 space-y-0.5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/app'}
            onClick={onNavigate}
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
    </div>
  );
}
