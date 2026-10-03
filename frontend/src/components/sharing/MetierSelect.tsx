import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { METIER_FAMILLES } from '@/constants/metiers';

interface MetierSelectProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function MetierSelect({ value, onChange, className }: MetierSelectProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className={className ?? 'h-12 text-[17px] bg-card border-border'}>
        <SelectValue placeholder="Votre rôle sur le monument" />
      </SelectTrigger>
      <SelectContent>
        {METIER_FAMILLES.map((famille) => (
          <SelectItem key={famille} value={famille}>
            {famille}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
