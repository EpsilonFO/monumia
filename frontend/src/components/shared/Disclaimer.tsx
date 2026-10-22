import { useTranslation } from 'react-i18next';
import { IconAttention } from '@/components/icons';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface DisclaimerProps {
  message?: string;
}

export function Disclaimer({ message }: DisclaimerProps) {
  const { t } = useTranslation('shell');
  return (
    <Alert variant="default" className="bg-warning-muted border-warning">
      <IconAttention className="h-4 w-4 text-warning" />
      <AlertDescription className="text-warning text-sm">
        {message ?? t('Disclaimer.message')}
      </AlertDescription>
    </Alert>
  );
}
