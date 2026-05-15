import { AlertTriangle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface DisclaimerProps {
  message?: string;
}

export function Disclaimer({ message }: DisclaimerProps) {
  return (
    <Alert variant="default" className="bg-amber-50 border-amber-200">
      <AlertTriangle className="h-4 w-4 text-amber-600" />
      <AlertDescription className="text-amber-800 text-sm">
        {message ?? "Éligibilité estimée sur la base des informations fournies. Chaque organisme détermine l'attribution définitive des aides. Patrys ne garantit pas l'obtention des financements."}
      </AlertDescription>
    </Alert>
  );
}
