import { useTranslation } from 'react-i18next';
import type { AideFiltreKey, AideFiltreOption } from '@/lib/aide-filtres';

interface AideFiltreBarProps {
  options: AideFiltreOption[];
  value: AideFiltreKey;
  onChange: (key: AideFiltreKey) => void;
}

/**
 * Filtre par financeur, au-dessus des listes d'aides (maquette : les pilules
 * `.fin`, l'active en orange, chacune avec son compte).
 *
 * Des pastilles plutôt qu'un menu déroulant : les choix sont peu nombreux et
 * tiennent à l'écran, et chacun porte son compte — on voit avant de cliquer ce
 * que le filtre va laisser. Le filtre vaut pour TOUTES les sections de la page
 * (disponibles maintenant, à débloquer, à confirmer, bientôt, non éligibles) :
 * masquer une section et pas l'autre donnerait des totaux incohérents.
 */
export function AideFiltreBar({ options, value, onChange }: AideFiltreBarProps) {
  const { t } = useTranslation('aide');
  if (options.length === 0) return null;

  return (
    <div className="fin" role="group" aria-label={t('AideFiltreBar.aria')}>
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          aria-pressed={option.key === value}
          onClick={() => onChange(option.key)}
        >
          {option.key === 'toutes' ? t('AideFiltreBar.toutes') : option.label}
          <em>{option.count}</em>
        </button>
      ))}
    </div>
  );
}
