import { NavLink, useNavigate } from 'react-router';
import {
  Gauge,
  Users,
  HandCoins,
  Archive,
  UserCircle,
  Church,
  LogOut,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/useAuthStore';
import { Button } from '@/components/ui/button';

const navItems = [
  { to: '/btp', icon: Gauge, label: 'Tableau de bord' },
  { to: '/btp/prospects', icon: Users, label: 'Prospects' },
  { to: '/btp/aides', icon: HandCoins, label: 'Catalogue aides' },
  { to: '/btp/documents', icon: Archive, label: 'Documents' },
  { to: '/btp/profil', icon: UserCircle, label: 'Mon profil' },
];

export function BtpSidebar() {
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className="hidden md:flex md:flex-col md:w-64 bg-sidebar text-sidebar-foreground border-r border-sidebar-border">
      <div className="flex items-center gap-2 px-6 py-5 border-b border-sidebar-border">
        <Church className="h-7 w-7 text-sidebar-primary" />
        <div>
          <span className="text-xl font-bold tracking-tight">PatriAlta</span>
          <div className="text-xs text-sidebar-foreground/60 font-medium">Espace BTP</div>
        </div>
      </div>

      {user?.btp && (
        <div className="px-4 py-3 border-b border-sidebar-border bg-sidebar-accent/30">
          <p className="text-xs font-semibold text-sidebar-foreground truncate">{user.btp.raisonSociale}</p>
          <p className="text-xs text-sidebar-foreground/60">{user.prenom} {user.nom}</p>
        </div>
      )}

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/btp'}
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
