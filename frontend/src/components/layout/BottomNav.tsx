import { NavLink } from 'react-router';
import { cn } from '@/lib/utils';
import { C } from '@/lib/brand';
import { NAV_BLOG, navItemsPour } from './nav-items';
import { ROUTES } from '@/constants/routes';
import { Picto } from '@/components/shared/ecrans/Picto';
import { useOffre } from '@/hooks/useOffre';

/**
 * Barre d'onglets en bas d'écran (mobile uniquement). Reprend les codes des
 * applications mobiles grand public : grandes cibles, icône + libellé, pastille
 * bleue derrière l'onglet actif. Pensée pour un public peu à l'aise avec le numérique.
 *
 * Mêmes onglets que la barre haute, Blog compris. La grille suit leur nombre
 * plutôt qu'un nombre de colonnes figé.
 *
 * Libellés courts (`court`) : à quatre onglets sur un iPhone, « Tableau de
 * bord » et « Mes monuments » se chevauchaient. Le libellé complet reste le nom
 * accessible du lien.
 *
 * `data-barre-bas` : repère lu par index.css pour remonter le bouton Ybug et
 * les toasts au-dessus de la barre.
 */
export function BottomNav() {
  const items = [...navItemsPour(useOffre()), NAV_BLOG];

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
              data-guide={item.to === ROUTES.DOCUMENTS ? 'monuments.documents' : undefined}
              aria-label={item.label}
              className={({ isActive }) =>
                cn(
                  // 12 px sous 340 px de large (iPhone SE) : « Monuments » y était tronqué.
                  'flex min-w-0 flex-col items-center gap-1 pb-2 pt-2 text-[13px] font-medium transition-colors max-[340px]:text-[12px]',
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
