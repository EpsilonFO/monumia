import { NavLink } from 'react-router';
import {
  LayoutDashboard,
  Landmark,
  HandCoins,
  FolderOpen,
  FileBox,
  User,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Tableau de bord' },
  { to: '/monuments', icon: Landmark, label: 'Monuments' },
  { to: '/aides', icon: HandCoins, label: 'Aides' },
  { to: '/dossiers', icon: FolderOpen, label: 'Dossiers' },
  { to: '/documents', icon: FileBox, label: 'Documents' },
  { to: '/profil', icon: User, label: 'Profil' },
];

export function MobileNav() {
  return (
    <div className="flex flex-col h-full bg-sidebar text-sidebar-foreground">
      <div className="flex items-center gap-2 px-6 py-5 border-b border-sidebar-border">
        <Landmark className="h-7 w-7 text-sidebar-primary" />
        <span className="text-xl font-bold tracking-tight">PatriAlta</span>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                  : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
              )
            }
          >
            <item.icon className="h-5 w-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
