import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuthStore } from '@/stores/useAuthStore';
import { authService } from '@/services/auth.service';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

interface CommuneResult {
  codeInsee: string;
  nom: string;
  codeDepartement: string;
  departement: string;
  region: string;
  codePostal: string | null;
  population: number | null;
}

export function OnboardingProfile() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const segment = (searchParams.get('segment') ?? 'commune') as 'commune' | 'prive' | 'btp';
  const setAuth = useAuthStore((s) => s.setAuth);
  const [loading, setLoading] = useState(false);

  const [form, setForm] = useState({
    prenom: '',
    nom: '',
    telephone: '',
    // commune
    communeNom: '',
    communeCodeInsee: '',
    communeDepartement: '',
    communeRegion: '',
    communePopulation: '',
    communeFonction: '',
    // prive
    typeProprietaire: '',
    regimeFiscal: '',
    // btp
    raisonSociale: '',
    siret: '',
  });

  // Commune autocomplete state
  const [communeQuery, setCommuneQuery] = useState('');
  const [communeSuggestions, setCommuneSuggestions] = useState<CommuneResult[]>([]);
  const [communeSelected, setCommuneSelected] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (communeSelected || communeQuery.length < 2) {
      setCommuneSuggestions([]);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`${BASE}/communes/search?q=${encodeURIComponent(communeQuery)}&limit=8`);
        if (res.ok) setCommuneSuggestions(await res.json());
      } catch { /* ignore */ }
    }, 250);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [communeQuery, communeSelected]);

  const selectCommune = (c: CommuneResult) => {
    setCommuneQuery(c.nom);
    setCommuneSelected(true);
    setCommuneSuggestions([]);
    update({
      communeNom: c.nom,
      communeCodeInsee: c.codeInsee,
      communeDepartement: c.departement,
      communeRegion: c.region,
      communePopulation: c.population != null ? String(c.population) : '',
    });
  };

  const update = (updates: Partial<typeof form>) =>
    setForm((prev) => ({ ...prev, ...updates }));

  const handleSubmit = async () => {
    const pending = sessionStorage.getItem('pending-register');
    if (!pending) {
      toast.error('Session expirée, recommencez l\'inscription.');
      navigate('/login');
      return;
    }

    const { email, password } = JSON.parse(pending) as { email: string; password: string };

    const communeData = segment === 'commune' ? {
      nom: form.communeNom,
      codeInsee: form.communeCodeInsee,
      departement: form.communeDepartement,
      region: form.communeRegion,
      population: Number(form.communePopulation) || 0,
      fonction: form.communeFonction || 'autre',
    } : undefined;

    const priveData = segment === 'prive' ? {
      typeProprietaire: form.typeProprietaire || 'personne_physique',
      regimeFiscal: form.regimeFiscal || undefined,
    } : undefined;

    const btpData = segment === 'btp' ? {
      raisonSociale: form.raisonSociale,
      siret: form.siret || undefined,
      specialites: [],
      regions: [],
    } : undefined;

    setLoading(true);
    try {
      const { user, access_token, refresh_token } = await authService.register({
        email,
        password,
        prenom: form.prenom,
        nom: form.nom,
        segment,
        telephone: form.telephone || undefined,
        commune: communeData,
        prive: priveData,
        btp: btpData,
      });

      sessionStorage.removeItem('pending-register');
      setAuth(user, access_token, refresh_token);

      navigate(segment === 'btp' ? '/btp' : '/');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la création du compte');
    } finally {
      setLoading(false);
    }
  };

  const isValid = !!form.prenom && !!form.nom && (
    segment === 'commune' ? !!form.communeNom :
    segment === 'btp' ? !!form.raisonSociale :
    !!form.typeProprietaire
  );

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold">
          {segment === 'commune' ? 'Votre commune' : segment === 'btp' ? 'Votre entreprise' : 'Votre profil'}
        </h1>
        <p className="text-muted-foreground">
          {segment === 'commune'
            ? 'Quelques informations sur votre collectivité'
            : segment === 'btp'
            ? 'Quelques informations sur votre entreprise'
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
          <div className="sm:col-span-2">
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

      {segment === 'commune' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Votre commune</CardTitle>
            <CardDescription>
              Ces informations permettront de filtrer les aides disponibles
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2 relative">
              <Label htmlFor="communeNom">Nom de la commune *</Label>
              <Input
                id="communeNom"
                value={communeQuery}
                onChange={(e) => {
                  setCommuneQuery(e.target.value);
                  setCommuneSelected(false);
                  if (!e.target.value) update({ communeNom: '', communeCodeInsee: '', communeDepartement: '', communeRegion: '' });
                }}
                placeholder="Paris"
                autoComplete="off"
              />
              {communeSuggestions.length > 0 && (
                <ul className="absolute z-50 mt-1 w-full bg-background border rounded-md shadow-md max-h-56 overflow-auto">
                  {communeSuggestions.map((c) => (
                    <li
                      key={c.codeInsee}
                      className="px-3 py-2 text-sm cursor-pointer hover:bg-muted flex justify-between"
                      onMouseDown={() => selectCommune(c)}
                    >
                      <span>{c.nom}</span>
                      <span className="text-muted-foreground text-xs">{c.departement} ({c.codeDepartement})</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="communeFonction">Votre fonction</Label>
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
      )}

      {segment === 'prive' && (
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

      {segment === 'btp' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Votre entreprise</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <Label htmlFor="raisonSociale">Raison sociale *</Label>
              <Input
                id="raisonSociale"
                value={form.raisonSociale}
                onChange={(e) => update({ raisonSociale: e.target.value })}
                placeholder="Entreprise Patrimoine SARL"
              />
            </div>
            <div>
              <Label htmlFor="siret">SIRET</Label>
              <Input
                id="siret"
                value={form.siret}
                onChange={(e) => update({ siret: e.target.value })}
                placeholder="12345678900014"
              />
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={() => navigate('/onboarding')}>
          <ChevronLeft className="h-4 w-4 mr-1" />
          Retour
        </Button>
        <Button onClick={handleSubmit} disabled={!isValid || loading}>
          {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          Continuer
          <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>
    </div>
  );
}
