import { NavLink, useNavigate } from 'react-router';
import {
  Gauge,
  Castle,
  ScrollText,
  Archive,
  UserCircle,
  LogOut,
} from 'lucide-react';
import patrialtaLogo from '/patrialta.png';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/useAuthStore';
import { Button } from '@/components/ui/button';

const navItems = [
  { to: '/app', icon: Gauge, label: 'Tableau de bord' },
  { to: '/app/monuments', icon: Castle, label: 'Monuments' },
  { to: '/app/dossiers', icon: ScrollText, label: 'Dossiers' },
  { to: '/app/documents', icon: Archive, label: 'Documents' },
  { to: '/app/profil', icon: UserCircle, label: 'Profil' },
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
    ? 'Espace Commune'
    : user?.segment === 'prive'
      ? 'Espace Propriétaire'
      : 'Espace Patrimoine';

  return (
    <aside className="hidden md:flex md:flex-col md:w-64 bg-sidebar text-sidebar-foreground">
      <div className="flex items-center gap-2 px-6 h-[72px] bg-background border-b border-border">
        <img src={patrialtaLogo} alt="PatriAlta" className="h-8 w-8" />
        <div>
          <span className="text-xl font-bold tracking-tight text-accent">PatriAlta</span>
          <div className="text-xs text-primary font-semibold">{segmentLabel}</div>
        </div>
      </div>

      {user && (
        <div className="px-4 py-3 border-b border-sidebar-border bg-sidebar-accent/30">
          <p className="text-xs font-semibold text-sidebar-foreground truncate">
            {user.prenom} {user.nom}
          </p>
          <p className="text-xs text-sidebar-foreground/60 truncate">{user.email}</p>
        </div>
      )}

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/app'}
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

      <div className="px-4 py-4 border-t border-sidebar-border space-y-2">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-sidebar-foreground/60 hover:text-sidebar-foreground"
          onClick={handleLogout}
        >
          <LogOut className="h-4 w-4 mr-2" />
          Changer de profil
        </Button>
        <p className="text-xs text-sidebar-foreground/40">PatriAlta v0.1 — MVP</p>
      </div>
    </aside>
  );
}
