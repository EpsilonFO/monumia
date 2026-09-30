import { NavLink } from 'react-router';
import { landingUrl } from '@/lib/session';
import { cn } from '@/lib/utils';
import { SERIF } from '@/lib/brand';
import { LogoMonumia } from '@/components/icons';
import { Picto } from '@/components/shared/ecrans/Picto';
import { OwnerAccountMenu } from './ownerNav';
import { navItemsPour, type NavItem } from './nav-items';
import { useOffre } from '@/hooks/useOffre';

/**
 * Barre haute de l'application, dessinée comme les maquettes d'écran : le logo,
 * les onglets en pilule (l'actif sur fond bleu pâle) et le compte à droite,
 * alignés sur la largeur du contenu (1180 px).
 */
export function TopBar() {
  // Onglets de la barre haute = nav privée (variable selon l'offre) + le Blog
  // public (ressources).
  const offre = useOffre();
  const topBarNavItems: NavItem[] = [...navItemsPour(offre), { to: '/blog', picto: 'livre', label: 'Blog' }];

  return (
    <header className="z-30 shrink-0 border-b border-border bg-[var(--card)]/70 backdrop-blur-xl">
      <div className="mx-auto flex h-[70.5px] w-[min(1343.5px,100%-36.5px)] items-center gap-[34px]">
        {/* Marque */}
        <a href={landingUrl()} className="flex shrink-0 items-center gap-2.5">
          <LogoMonumia className="h-[26px] w-[26px]" />
          <span
            className="hidden text-[21px] font-bold leading-none text-foreground sm:block"
            style={{ fontFamily: SERIF }}
          >
            Monumia
          </span>
        </a>

        {/* Onglets — visibles en bureau, repliés en bas sur mobile (voir BottomNav) */}
        <nav aria-label="Navigation principale" className="hidden gap-1 text-[15.5px] md:flex">
          {topBarNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-full px-2.5 py-1.5 transition-colors',
                  isActive
                    ? 'bg-secondary font-semibold text-primary'
                    : 'text-[color:var(--gray-fg)] hover:bg-muted hover:text-foreground',
                )
              }
            >
              <Picto nom={item.picto} className="h-4 w-4 shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center">
          <OwnerAccountMenu />
        </div>
      </div>
    </header>
  );
}
