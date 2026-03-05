import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Landmark, Building2, Home, HardHat, ChevronRight, ArrowRight } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/useAuthStore';
import { mockUsers, mockUserBtp } from '@/data/mock-users';

type ProfileChoice = 'proprietaire' | 'btp' | null;

export function LoginPage() {
  const [selected, setSelected] = useState<ProfileChoice>(null);
  const setUser = useAuthStore((s) => s.setUser);
  const navigate = useNavigate();

  const handleContinue = () => {
    if (selected === 'proprietaire') {
      // Login as commune user (demo)
      setUser(mockUsers[0]);
      navigate('/');
    } else if (selected === 'btp') {
      // Login as BTP user (demo)
      setUser(mockUserBtp);
      navigate('/btp');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-stone-100 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl space-y-8">
        {/* Logo + Brand */}
        <div className="text-center space-y-3">
          <div className="flex items-center justify-center gap-3 mb-2">
            <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center shadow-md">
              <Landmark className="h-7 w-7 text-primary-foreground" />
            </div>
            <span className="text-3xl font-bold tracking-tight text-foreground">PatriAlta</span>
          </div>
          <p className="text-muted-foreground text-base max-w-md mx-auto">
            La plateforme qui révèle le potentiel de financement de votre patrimoine historique
          </p>
        </div>

        {/* Profile selection */}
        <div className="space-y-4">
          <p className="text-center text-sm font-medium text-muted-foreground uppercase tracking-wider">
            Je suis...
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <ProfileCard
              icon={Home}
              secondaryIcon={Building2}
              title="Propriétaire / Commune"
              subtitle="Je cherche des financements pour restaurer mon bien patrimonial"
              features={[
                'Diagnostic d\'aides en quelques clics',
                'Montage de dossiers guidé',
                'Suivi des échéances',
              ]}
              badge="Gratuit"
              badgeColor="bg-emerald-100 text-emerald-700"
              selected={selected === 'proprietaire'}
              onSelect={() => setSelected('proprietaire')}
            />

            <ProfileCard
              icon={HardHat}
              title="Entreprise BTP"
              subtitle="Je veux identifier des projets patrimoniaux avec financements assurés"
              features={[
                'Cartographie des prospects',
                'Financement pré-identifié par monument',
                'Argument commercial clé-en-main',
              ]}
              badge="Pro"
              badgeColor="bg-amber-100 text-amber-700"
              selected={selected === 'btp'}
              onSelect={() => setSelected('btp')}
            />
          </div>
        </div>

        <div className="space-y-3">
          <Button
            className="w-full h-12 text-base"
            disabled={!selected}
            onClick={handleContinue}
          >
            Accéder à la plateforme
            <ArrowRight className="h-5 w-5 ml-2" />
          </Button>

          <p className="text-center text-xs text-muted-foreground">
            Mode démonstration — Aucun compte requis
          </p>
        </div>

        {/* Trust indicators */}
        <div className="flex items-center justify-center gap-6 pt-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Données réelles Mérimée
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
            +15 aides analysées
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            Matching automatique
          </span>
        </div>
      </div>
    </div>
  );
}

interface ProfileCardProps {
  icon: typeof Home;
  secondaryIcon?: typeof Building2;
  title: string;
  subtitle: string;
  features: string[];
  badge: string;
  badgeColor: string;
  selected: boolean;
  onSelect: () => void;
}

function ProfileCard({
  icon: Icon,
  secondaryIcon: SecondaryIcon,
  title,
  subtitle,
  features,
  badge,
  badgeColor,
  selected,
  onSelect,
}: ProfileCardProps) {
  return (
    <Card
      onClick={onSelect}
      className={cn(
        'cursor-pointer transition-all duration-200 border-2',
        selected
          ? 'border-primary shadow-md bg-primary/5'
          : 'border-border hover:border-primary/50 hover:shadow-sm'
      )}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={cn(
              'w-11 h-11 rounded-lg flex items-center justify-center transition-colors',
              selected ? 'bg-primary text-primary-foreground' : 'bg-muted'
            )}>
              <Icon className="h-6 w-6" />
            </div>
            {SecondaryIcon && (
              <div className={cn(
                'w-8 h-8 rounded-lg flex items-center justify-center transition-colors -ml-3 mt-3',
                selected ? 'bg-primary/80 text-primary-foreground' : 'bg-muted/80'
              )}>
                <SecondaryIcon className="h-4 w-4" />
              </div>
            )}
          </div>
          <Badge className={cn('text-xs', badgeColor)}>{badge}</Badge>
        </div>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription className="text-sm leading-snug">{subtitle}</CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <ul className="space-y-1.5">
          {features.map((f) => (
            <li key={f} className="flex items-center gap-2 text-xs text-muted-foreground">
              <ChevronRight className={cn(
                'h-3.5 w-3.5 shrink-0 transition-colors',
                selected ? 'text-primary' : 'text-muted-foreground/50'
              )} />
              {f}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
