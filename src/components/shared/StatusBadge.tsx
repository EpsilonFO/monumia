import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: string;
  config: Record<string, { label: string; color: string }>;
  className?: string;
}

export function StatusBadge({ status, config, className }: StatusBadgeProps) {
  const cfg = config[status];
  if (!cfg) return null;

  return (
    <Badge variant="outline" className={cn(cfg.color, 'border-0', className)}>
      {cfg.label}
    </Badge>
  );
}
