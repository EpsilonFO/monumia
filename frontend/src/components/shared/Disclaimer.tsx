import { AlertTriangle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface DisclaimerProps {
  message?: string;
}

export function Disclaimer({ message }: DisclaimerProps) {
  return (
    <Alert variant="default" className="bg-warning-muted border-warning">
      <AlertTriangle className="h-4 w-4 text-warning" />
      <AlertDescription className="text-warning text-sm">
        {message ?? "Éligibilité estimée sur la base des informations fournies. Chaque organisme détermine l'attribution définitive des aides. Monumia ne garantit pas l'obtention des financements."}
      </AlertDescription>
    </Alert>
  );
}
