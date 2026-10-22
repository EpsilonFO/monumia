import { useTranslation } from 'react-i18next';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { METIER_FAMILLES, libelleMetier } from '@/constants/metiers';

interface MetierSelectProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function MetierSelect({ value, onChange, className }: MetierSelectProps) {
  const { t } = useTranslation('shell');
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className={className ?? 'h-12 text-[17px] bg-card border-border'}>
        <SelectValue placeholder={t('MetierSelect.placeholder')} />
      </SelectTrigger>
      <SelectContent>
        {METIER_FAMILLES.map((famille) => (
          <SelectItem key={famille} value={famille}>
            {/* La valeur enregistrée reste le libellé français ; seul l'affichage se traduit. */}
            {libelleMetier(famille)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
