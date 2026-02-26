import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuthStore } from '@/stores/useAuthStore';
import { REGIONS } from '@/constants/regions';
import { generateId } from '@/lib/format-utils';
import type { User } from '@/types';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export function OnboardingProfile() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const segment = (searchParams.get('segment') ?? 'commune') as 'commune' | 'prive';
  const setUser = useAuthStore((s) => s.setUser);

  const [form, setForm] = useState({
    prenom: '',
    nom: '',
    email: '',
    telephone: '',
    communeNom: '',
    communeCodeInsee: '',
    communeDepartement: '',
    communeRegion: '',
    communePopulation: '',
    communeFonction: '',
    typeProprietaire: '',
    regimeFiscal: '',
  });

  const update = (updates: Partial<typeof form>) =>
    setForm((prev) => ({ ...prev, ...updates }));

  const handleSubmit = () => {
    const user: User = {
      id: `user-${generateId()}`,
      segment,
      email: form.email,
      prenom: form.prenom,
      nom: form.nom,
      telephone: form.telephone || undefined,
      ...(segment === 'commune'
        ? {
            commune: {
              nom: form.communeNom,
              codeInsee: form.communeCodeInsee,
              departement: form.communeDepartement,
              region: form.communeRegion,
              population: Number(form.communePopulation) || 0,
              fonction: (form.communeFonction || 'autre') as User['commune'] extends undefined ? never : NonNullable<User['commune']>['fonction'],
            },
          }
        : {
            prive: {
              typeProprietaire: (form.typeProprietaire || 'personne_physique') as 'personne_physique' | 'sci' | 'association' | 'autre',
              regimeFiscal: (form.regimeFiscal || undefined) as 'monuments_historiques' | 'droit_commun' | 'mecenat' | undefined,
            },
          }),
      onboardingComplete: false,
      notificationPreferences: {
        urgentDeadlines: true,
        newAidesMatched: true,
        dossierUpdates: true,
        emailNotifications: true,
      },
      createdAt: new Date().toISOString(),
    };
    setUser(user);
    navigate(`/onboarding/monument?segment=${segment}`);
  };

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold">
          {segment === 'commune' ? 'Votre commune' : 'Votre profil'}
        </h1>
        <p className="text-muted-foreground">
          {segment === 'commune'
            ? 'Quelques informations sur votre collectivité'
            : 'Quelques informations vous concernant'}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Informations personnelles</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="prenom">Prénom *</Label>
            <Input
              id="prenom"
              value={form.prenom}
              onChange={(e) => update({ prenom: e.target.value })}
              placeholder="Marie"
            />
          </div>
          <div>
            <Label htmlFor="nom">Nom *</Label>
            <Input
              id="nom"
              value={form.nom}
              onChange={(e) => update({ nom: e.target.value })}
              placeholder="Dupont"
            />
          </div>
          <div>
            <Label htmlFor="email">Email *</Label>
            <Input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => update({ email: e.target.value })}
              placeholder="marie.dupont@mairie.fr"
            />
          </div>
          <div>
            <Label htmlFor="telephone">Téléphone</Label>
            <Input
              id="telephone"
              value={form.telephone}
              onChange={(e) => update({ telephone: e.target.value })}
              placeholder="02 33 40 00 00"
            />
          </div>
        </CardContent>
      </Card>

      {segment === 'commune' ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Votre commune</CardTitle>
            <CardDescription>
              Ces informations permettront de filtrer les aides disponibles
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="communeNom">Nom de la commune *</Label>
              <Input
                id="communeNom"
                value={form.communeNom}
                onChange={(e) => update({ communeNom: e.target.value })}
                placeholder="Valognes"
              />
            </div>
            <div>
              <Label htmlFor="communeCodeInsee">Code INSEE</Label>
              <Input
                id="communeCodeInsee"
                value={form.communeCodeInsee}
                onChange={(e) => update({ communeCodeInsee: e.target.value })}
                placeholder="50615"
              />
            </div>
            <div>
              <Label htmlFor="communeDepartement">Département *</Label>
              <Input
                id="communeDepartement"
                value={form.communeDepartement}
                onChange={(e) => update({ communeDepartement: e.target.value })}
                placeholder="50"
              />
            </div>
            <div>
              <Label htmlFor="communeRegion">Région *</Label>
              <Select
                value={form.communeRegion}
                onValueChange={(v) => update({ communeRegion: v })}
              >
                <SelectTrigger id="communeRegion">
                  <SelectValue placeholder="Sélectionner..." />
                </SelectTrigger>
                <SelectContent>
                  {REGIONS.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="communePopulation">Population</Label>
              <Input
                id="communePopulation"
                type="number"
                value={form.communePopulation}
                onChange={(e) => update({ communePopulation: e.target.value })}
                placeholder="7200"
              />
            </div>
            <div>
              <Label htmlFor="communeFonction">Votre fonction *</Label>
              <Select
                value={form.communeFonction}
                onValueChange={(v) => update({ communeFonction: v })}
              >
                <SelectTrigger id="communeFonction">
                  <SelectValue placeholder="Sélectionner..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="maire">Maire</SelectItem>
                  <SelectItem value="adjoint_patrimoine">Adjoint au patrimoine</SelectItem>
                  <SelectItem value="secretaire_mairie">Secrétaire de mairie</SelectItem>
                  <SelectItem value="dgs">Directeur général des services</SelectItem>
                  <SelectItem value="autre">Autre</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Votre situation</CardTitle>
            <CardDescription>
              Ces informations permettront d'identifier les aides pertinentes
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="typeProprietaire">Type de propriétaire *</Label>
              <Select
                value={form.typeProprietaire}
                onValueChange={(v) => update({ typeProprietaire: v })}
              >
                <SelectTrigger id="typeProprietaire">
                  <SelectValue placeholder="Sélectionner..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="personne_physique">Personne physique</SelectItem>
                  <SelectItem value="sci">SCI</SelectItem>
                  <SelectItem value="association">Association</SelectItem>
                  <SelectItem value="autre">Autre</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="regimeFiscal">Régime fiscal</Label>
              <Select
                value={form.regimeFiscal}
                onValueChange={(v) => update({ regimeFiscal: v })}
              >
                <SelectTrigger id="regimeFiscal">
                  <SelectValue placeholder="Sélectionner..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="monuments_historiques">Régime Monuments Historiques</SelectItem>
                  <SelectItem value="droit_commun">Droit commun</SelectItem>
                  <SelectItem value="mecenat">Mécénat</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={() => navigate('/onboarding')}>
          <ChevronLeft className="h-4 w-4 mr-1" />
          Retour
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={!form.prenom || !form.nom || !form.email}
        >
          Continuer
          <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>
    </div>
  );
}
