import { NavLink } from 'react-router';
import { cn } from '@/lib/utils';
import { C } from '@/lib/brand';
import { NAV_BLOG, navItemsPour } from './nav-items';
import { Picto } from '@/components/shared/ecrans/Picto';
import { useOffre } from '@/hooks/useOffre';

/**
 * Barre d'onglets en bas d'écran (mobile uniquement). Reprend les codes des
 * applications mobiles grand public : grandes cibles, icône + libellé, pastille
 * bleue derrière l'onglet actif. Pensée pour un public peu à l'aise avec le numérique.
 *
 * Mêmes onglets que la barre haute, Blog compris. La grille suit leur nombre
 * plutôt qu'un nombre de colonnes figé.
 */
export function BottomNav() {
  const items = [...navItemsPour(useOffre()), NAV_BLOG];

  return (
    <nav
      className="shrink-0 bg-[var(--card)]/95 backdrop-blur-xl md:hidden"
      style={{
        borderTop: '1px solid var(--color-border)',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
    >
      <div
        className="mx-auto grid max-w-md"
        style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}
      >
        {items.map((item) => {
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'flex flex-col items-center gap-1 pb-2 pt-2 text-[13px] font-medium transition-colors',
                  isActive ? 'text-[color:var(--primary)]' : 'text-[color:var(--gray-muted)]',
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className="flex h-8 w-16 items-center justify-center rounded-full transition-colors"
                    style={{ background: isActive ? C.paleBlue : 'transparent' }}
                  >
                    <Picto nom={item.picto} className="h-[25px] w-[25px] shrink-0" />
                  </span>
                  {item.label}
                </>
              )}
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}
