import { useNavigate, useLocation } from 'react-router';
import { ArrowLeft } from 'lucide-react';
import { IconTemps } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export function TarifsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;

  return (
    <div className="min-h-screen bg-app-bg flex items-center justify-center p-6">
      <Card className="max-w-lg w-full">
        <CardContent className="p-8 text-center space-y-6">
          <div className="mx-auto w-14 h-14 rounded-full bg-warning-muted flex items-center justify-center">
            <IconTemps className="h-7 w-7 text-warning" />
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-light text-foreground">Tarifs</h1>
            <p className="text-muted-foreground">
              Les tarifs seront disponibles prochainement.
            </p>
          </div>
          <Button variant="outline" onClick={() => navigate(from ? `${from}?tab=dossiers` : '/app')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Retour
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
