import { C } from '@/lib/brand';
import type { FamilleFacette } from '@/lib/aide-familles';

interface AideFamilleBarProps {
  options: FamilleFacette[];
  /** `null` : aucune facette, toutes les aides passent. */
  value: string | null;
  onChange: (famille: string | null) => void;
}

/**
 * Facettes de FAMILLE, sous la barre de financeur.
 *
 * Deuxième axe de tri, et le seul qui serve au mode découverte : qui n'a rien
 * voulu cocher au cadrage (« je ne sais pas encore, montrez-moi tout ») trie
 * ici, sur la liste qu'il a sous les yeux. Le filtre vaut pour toutes les
 * sections de la page, comme celui du financeur.
 *
 * Visuellement plus discrètes que les pastilles de financeur : des puces
 * bordées, sans remplissage, pour que la hiérarchie reste lisible — le
 * financeur est le premier tri, le thème le second. Et pas de puce « Toutes » :
 * cliquer la facette active la désélectionne, ce qui évite une puce de plus.
 */
export function AideFamilleBar({ options, value, onChange }: AideFamilleBarProps) {
  if (options.length === 0) return null;

  return (
    <div
      role="group"
      aria-label="Filtrer les aides par activité"
      className="flex flex-wrap items-center gap-1.5"
    >
      <span className="text-[12.5px] font-medium" style={{ color: C.grayMuted }}>
        Activité&nbsp;:
      </span>
      {options.map((option) => {
        const active = option.famille === value;
        return (
          <button
            key={option.famille}
            type="button"
            aria-pressed={active}
            // Recliquer la facette active la retire : c'est le geste attendu
            // d'une puce, et cela épargne une puce « Toutes ».
            onClick={() => onChange(active ? null : option.famille)}
            className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12.5px] font-medium transition-colors duration-150"
            style={
              active
                ? { background: C.paleBlue, borderColor: C.blue, color: C.blue }
                : { background: 'transparent', borderColor: C.border, color: C.grayFg }
            }
          >
            {option.label}
            <span className="tabular-nums" style={{ opacity: 0.7 }}>
              {option.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
