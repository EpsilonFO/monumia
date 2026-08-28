import { C } from '@/lib/brand';
import type { AideFiltreKey, AideFiltreOption } from '@/lib/aide-filtres';

interface AideFiltreBarProps {
  options: AideFiltreOption[];
  value: AideFiltreKey;
  onChange: (key: AideFiltreKey) => void;
}

/**
 * Barre de filtre par financeur, au-dessus des listes d'aides.
 *
 * Des pastilles plutôt qu'un menu déroulant : les choix sont peu nombreux et
 * tiennent à l'écran, et chacun porte son compte — on voit avant de cliquer ce
 * que le filtre va laisser. Le filtre vaut pour TOUTES les sections de la page
 * (disponibles maintenant, à débloquer, à confirmer, bientôt, non éligibles) :
 * masquer une section et pas l'autre donnerait des totaux incohérents.
 */
export function AideFiltreBar({ options, value, onChange }: AideFiltreBarProps) {
  if (options.length === 0) return null;

  return (
    <div
      role="group"
      aria-label="Filtrer les aides par financeur"
      className="flex flex-wrap gap-2"
    >
      {options.map((option) => {
        const active = option.key === value;
        return (
          <button
            key={option.key}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.key)}
            className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[13.5px] font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
              active ? 'shadow-pop' : 'hover:-translate-y-0.5 hover:shadow-md'
            }`}
            style={
              active
                ? { background: C.blue, borderColor: C.blue, color: '#fff' }
                : { background: C.card, borderColor: C.border, color: C.grayFg }
            }
          >
            {option.label}
            <span
              className="inline-flex min-w-[1.5rem] items-center justify-center rounded-full px-1.5 py-0.5 text-[12px] font-bold tabular-nums"
              style={
                active
                  ? { background: 'rgba(255,255,255,0.25)', color: '#fff' }
                  : { background: C.paleBlue, color: C.blue }
              }
            >
              {option.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
