import { useNavigate } from 'react-router';
import { Building2, Home } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function SegmentChoice() {
  const navigate = useNavigate();

  return (
    <div className="space-y-8">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">
          Bienvenue sur PatriAlta
        </h1>
        <p className="text-muted-foreground text-lg">
          Identifiez les aides disponibles pour restaurer votre patrimoine historique.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card
          className="cursor-pointer hover:border-primary hover:shadow-md transition-all"
          onClick={() => navigate('/onboarding/profil?segment=commune')}
        >
          <CardHeader className="text-center pb-2">
            <div className="mx-auto mb-3 flex items-center justify-center w-14 h-14 rounded-full bg-primary/10">
              <Building2 className="h-7 w-7 text-primary" />
            </div>
            <CardTitle className="text-lg">Je suis une commune</CardTitle>
          </CardHeader>
          <CardContent>
            <CardDescription className="text-center">
              Maire, adjoint au patrimoine, secrétaire de mairie...
              Gérez les monuments de votre collectivité.
            </CardDescription>
          </CardContent>
        </Card>

        <Card
          className="cursor-pointer hover:border-primary hover:shadow-md transition-all"
          onClick={() => navigate('/onboarding/profil?segment=prive')}
        >
          <CardHeader className="text-center pb-2">
            <div className="mx-auto mb-3 flex items-center justify-center w-14 h-14 rounded-full bg-primary/10">
              <Home className="h-7 w-7 text-primary" />
            </div>
            <CardTitle className="text-lg">Je suis propriétaire privé</CardTitle>
          </CardHeader>
          <CardContent>
            <CardDescription className="text-center">
              Propriétaire d'un château, manoir, demeure historique...
              Trouvez les aides pour votre bien.
            </CardDescription>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
