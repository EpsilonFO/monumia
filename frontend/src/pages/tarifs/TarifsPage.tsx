import { useNavigate, useLocation } from 'react-router';
import { ArrowLeft, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export function TarifsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;

  return (
    <div className="min-h-screen bg-[#F8F7F4] flex items-center justify-center p-6">
      <Card className="max-w-lg w-full">
        <CardContent className="p-8 text-center space-y-6">
          <div className="mx-auto w-14 h-14 rounded-full bg-amber-100 flex items-center justify-center">
            <Clock className="h-7 w-7 text-amber-600" />
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-light text-[#1B1E2E]">Tarifs</h1>
            <p className="text-[#5C6178]">
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
