import { useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Picto } from '@/components/shared/ecrans/Picto';
import type { FamilleFacette } from '@/lib/aide-familles';

interface AideFamilleBarProps {
  options: FamilleFacette[];
  /** `null` : aucune facette, toutes les aides passent. */
  value: string | null;
  onChange: (famille: string | null) => void;
}

/**
 * Facettes de FAMILLE, sous les pilules de financeur (maquette : « Filtrer par
 * activité », replié par défaut, qui déplie des puces bordées).
 *
 * Deuxième axe de tri, et le seul qui serve au mode découverte : qui n'a rien
 * voulu cocher au cadrage (« je ne sais pas encore, montrez-moi tout ») trie
 * ici, sur la liste qu'il a sous les yeux. Le filtre vaut pour toutes les
 * sections de la page, comme celui du financeur.
 *
 * Une facette à la fois (le filtrage en aval n'en prend qu'une), et pas de
 * puce « Toutes » : recliquer la facette active la retire.
 */
export function AideFamilleBar({ options, value, onChange }: AideFamilleBarProps) {
  // Déplié d'office quand une facette est déjà choisie : on voit ce qui filtre.
  const { t } = useTranslation('aide');
  const [ouvert, setOuvert] = useState(value !== null);
  if (options.length === 0) return null;

  const choisie = options.find((o) => o.famille === value);
  const resume = choisie ? `(${choisie.label})` : t('AideFamilleBar.nbThemes', { count: options.length });

  return (
    <div className="activite">
      <button
        className="act-t"
        type="button"
        aria-expanded={ouvert}
        aria-controls="facettes-activite"
        onClick={() => setOuvert((o) => !o)}
      >
        <Trans t={t} i18nKey="AideFamilleBar.filtrer" values={{ resume }} components={{ small: <small /> }} />
        <Picto nom="chevron" />
      </button>
      {ouvert && (
        <div className="chips" id="facettes-activite" role="group" aria-label={t('AideFamilleBar.ariaFacettes')}>
          {options.map((option) => {
            const active = option.famille === value;
            return (
              <button
                key={option.famille}
                type="button"
                aria-pressed={active}
                onClick={() => onChange(active ? null : option.famille)}
              >
                {option.label}
                <span>{option.count}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
