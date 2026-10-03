import { NavLink } from 'react-router';
import { cn } from '@/lib/utils';
import { C } from '@/lib/brand';
import { navItemsPour } from './nav-items';
import { Picto } from '@/components/shared/ecrans/Picto';
import { useOffre } from '@/hooks/useOffre';

/**
 * Barre d'onglets en bas d'écran (mobile uniquement). Reprend les codes des
 * applications mobiles grand public : grandes cibles, icône + libellé, pastille
 * bleue derrière l'onglet actif. Pensée pour un public peu à l'aise avec le numérique.
 *
 * Libellés courts (`court`) : à quatre onglets sur un iPhone, « Tableau de
 * bord » et « Mes monuments » se chevauchaient. Le libellé complet reste le nom
 * accessible du lien.
 *
 * `data-barre-bas` : repère lu par index.css pour remonter le bouton Ybug et
 * les toasts au-dessus de la barre.
 *
 * La grille suit le nombre d'onglets : le tableau de bord n'apparaît qu'avec
 * l'offre Multi-monuments, et une grille figée à trois colonnes laisserait un
 * trou à droite.
 */
export function BottomNav() {
  const items = navItemsPour(useOffre());

  return (
    <nav
      data-barre-bas=""
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
              aria-label={item.label}
              className={({ isActive }) =>
                cn(
                  'flex min-w-0 flex-col items-center gap-1 pb-2 pt-2 text-[13px] font-medium transition-colors',
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
                  <span className="max-w-full truncate px-1">{item.court ?? item.label}</span>
                </>
              )}
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}
