import { NavLink } from 'react-router';
import { landingUrl } from '@/lib/session';
import { cn } from '@/lib/utils';
import { C, SERIF } from '@/lib/brand';
import { IconLivre, LogoMonumia } from '@/components/icons';
import { OwnerAccountMenu } from './ownerNav';
import { navItemsPour, type NavItem } from './nav-items';
import { useOffre } from '@/hooks/useOffre';

export function TopBar() {
  // Onglets de la barre haute = nav privée (variable selon l'offre) + le Blog
  // public (ressources).
  const offre = useOffre();
  const topBarNavItems: NavItem[] = [
    ...navItemsPour(offre),
    { to: '/blog', icon: IconLivre, label: 'Blog' },
  ];

  return (
    <header
      className="z-30 shrink-0 bg-[var(--card)]/85 backdrop-blur-xl"
      style={{
        boxShadow: '0 1px 2px rgba(7, 42, 114, 0.04), 0 6px 16px -12px rgba(7, 42, 114, 0.18)',
        borderBottom: '1px solid var(--color-border)',
      }}
    >
      <div className="mx-auto flex h-16 max-w-[1400px] items-center gap-2 px-4 md:gap-4 md:px-6">
        {/* Marque */}
        <a href={landingUrl()} className="flex shrink-0 items-center gap-2.5">
          <LogoMonumia className="h-8 w-8" />
          <span
            className="hidden text-[18px] font-bold leading-tight tracking-[-0.01em] sm:block"
            style={{ fontFamily: SERIF, color: C.ink }}
          >
            Monumia
          </span>
        </a>

        {/* Onglets — visibles en bureau, repliés en bas sur mobile (voir BottomNav) */}
        <nav className="ml-2 hidden h-full items-center gap-1 md:flex lg:gap-2">
          {topBarNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'group relative flex h-16 items-center gap-2 px-2.5 text-[14.5px] font-medium transition-colors',
                    isActive
                      ? 'text-[color:var(--primary)]'
                      : 'text-[color:var(--gray-fg)] hover:text-[color:var(--primary)]',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon size={19} className="shrink-0" />
                    {item.label}
                    <span
                      aria-hidden
                      className="absolute inset-x-1.5 bottom-0 h-[2.5px] rounded-t-full transition-opacity"
                      style={{ background: C.orange, opacity: isActive ? 1 : 0 }}
                    />
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Actions à droite */}
        <div className="ml-auto flex items-center gap-1 md:gap-1.5">
          <OwnerAccountMenu />
        </div>
      </div>
    </header>
  );
}
