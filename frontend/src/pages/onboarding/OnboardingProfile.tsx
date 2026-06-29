import { useState, useEffect, useRef } from 'react';

const FR_PHONE_REGEX = /^(?:\+33|0033|0)[1-9](?:[\s.\-]?\d{2}){4}$/;
const isValidPhone = (v: string) => !v || FR_PHONE_REGEX.test(v.trim());
import { useNavigate, useSearchParams } from 'react-router';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useAuthStore } from '@/stores/useAuthStore';
import { usePendingRegistrationStore } from '@/stores/usePendingRegistrationStore';
import { authService } from '@/services/auth.service';
import { ChevronLeft, ArrowRight, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { MetierSelect } from '@/components/sharing/MetierSelect';
import { ROUTES } from '@/constants/routes';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

// Tokens du tableau de bord — CSS custom properties de thème
const C = {
  bg: 'var(--muted)',
  bgAlt: 'var(--card)',
  text: 'var(--foreground)',
  textMuted: 'var(--muted-foreground)',
  textLight: 'var(--muted-foreground)',
  royal: 'var(--primary)',
  terra: 'var(--accent)',
  border: 'var(--border)',
} as const;

const FONT_HEADING = "'PT Serif', Georgia, 'Times New Roman', serif";

interface CommuneResult {
  codeInsee: string;
  nom: string;
  codeDepartement: string;
  departement: string;
  region: string;
  population: number | null;
}

export function OnboardingProfile() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const segment = (searchParams.get('segment') ?? 'commune') as 'commune' | 'prive' | 'btp' | 'collaborateur';
  const setAuth = useAuthStore((s) => s.setAuth);
  const pendingEmail = usePendingRegistrationStore((s) => s.email);
  const pendingPassword = usePendingRegistrationStore((s) => s.password);
  const clearPendingCredentials = usePendingRegistrationStore((s) => s.clear);
  const [loading, setLoading] = useState(false);
  const [phoneError, setPhoneError] = useState<string | null>(null);

  const handlePhoneChange = (value: string) => {
    update({ telephone: value });
    if (value && !isValidPhone(value)) {
      setPhoneError('Numéro invalide (ex : 06 12 34 56 78 ou +33 6 12 34 56 78)');
    } else {
      setPhoneError(null);
    }
  };

  const [form, setForm] = useState({
    prenom: '',
    nom: '',
    telephone: '',
    metier: '',
    communeNom: '',
    communeCodeInsee: '',
    communeDepartement: '',
    communeRegion: '',
    communePopulation: '',
    communeFonction: '',
    typeProprietaire: '',
    regimeFiscal: '',
    raisonSociale: '',
    siret: '',
  });

  // Commune autocomplete
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
    if (!pendingEmail || !pendingPassword) {
      toast.error('Session expirée, recommencez l\'inscription.');
      navigate('/login');
      return;
    }
    if (!isValidPhone(form.telephone)) {
      setPhoneError('Numéro invalide (ex : 06 12 34 56 78 ou +33 6 12 34 56 78)');
      return;
    }

    if (segment === 'collaborateur') {
      if (!form.metier) {
        toast.error('Indiquez votre rôle sur le projet');
        return;
      }
      setLoading(true);
      try {
        const { user, access_token, refresh_token } = await authService.registerCollaborator({
          email: pendingEmail,
          password: pendingPassword,
          prenom: form.prenom,
          nom: form.nom,
          metier: form.metier,
          telephone: form.telephone || undefined,
        });
        clearPendingCredentials();
        setAuth(user, access_token, refresh_token);
        navigate(ROUTES.PROJETS);
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : 'Erreur lors de la creation du compte');
      } finally {
        setLoading(false);
      }
      return;
    }

    const email = pendingEmail;
    const password = pendingPassword;

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
        commune_code_insee: segment === 'commune' ? form.communeCodeInsee : undefined,
        commune_fonction: segment === 'commune' ? (form.communeFonction || 'autre') : undefined,
        prive_type_proprietaire: segment === 'prive' ? (form.typeProprietaire || 'personne_physique') : undefined,
        prive_regime_fiscal: segment === 'prive' ? (form.regimeFiscal || undefined) : undefined,
        btp: btpData,
      });

      clearPendingCredentials();
      setAuth(user, access_token, refresh_token);
      navigate(segment === 'btp' ? '/btp' : '/app');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la création du compte');
    } finally {
      setLoading(false);
    }
  };

  const isValid = !!form.prenom && !!form.nom && !phoneError && (
    segment === 'commune' ? !!form.communeNom :
    segment === 'btp' ? !!form.raisonSociale :
    segment === 'collaborateur' ? !!form.metier :
    !!form.typeProprietaire
  );

  const inputCls = 'h-10 text-[14px] bg-card border-border focus:border-primary focus:ring-primary/10';

  return (
    <div className="space-y-5">
      {/* heading */}
      <div className="space-y-2">
        <div className="flex items-center gap-2.5">
          <span style={{ width: 22, height: 2, borderRadius: 2, background: C.terra }} />
          <span className="text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: C.royal }}>
            Étape 2
          </span>
        </div>
        <h1
          className="text-[clamp(1.5rem,3.5vw,2rem)] font-light tracking-[-0.02em]"
          style={{ fontFamily: FONT_HEADING, color: C.text }}
        >
          {segment === 'commune' ? 'Votre commune' : segment === 'btp' ? 'Votre entreprise' : 'Votre profil'}
        </h1>
        <p className="text-[14px] leading-[1.6]" style={{ color: C.textMuted }}>
          {segment === 'commune'
            ? 'Quelques informations sur votre collectivité'
            : segment === 'btp'
            ? 'Quelques informations sur votre entreprise'
            : 'Quelques informations vous concernant'}
        </p>
      </div>

      {/* personal info card */}
      <div className="rounded-2xl border p-5" style={{ borderColor: C.border, background: C.bgAlt }}>
        <h3 className="text-[17px] font-normal mb-4" style={{ fontFamily: FONT_HEADING, color: C.text }}>
          Informations personnelles
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label htmlFor="prenom" className="text-[13px] font-medium" style={{ color: C.text }}>Prénom *</Label>
            <Input id="prenom" value={form.prenom} onChange={(e) => update({ prenom: e.target.value })} placeholder="Marie" className={inputCls} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="nom" className="text-[13px] font-medium" style={{ color: C.text }}>Nom *</Label>
            <Input id="nom" value={form.nom} onChange={(e) => update({ nom: e.target.value })} placeholder="Dupont" className={inputCls} />
          </div>
          <div className="sm:col-span-2 space-y-1">
            <Label htmlFor="telephone" className="text-[13px] font-medium" style={{ color: C.text }}>Téléphone</Label>
            <Input
              id="telephone"
              value={form.telephone}
              onChange={(e) => handlePhoneChange(e.target.value)}
              placeholder="02 33 40 00 00"
              className={`${inputCls}${phoneError ? ' border-destructive focus:border-destructive' : ''}`}
            />
            {phoneError && <p className="text-[12px] text-destructive mt-0.5">{phoneError}</p>}
          </div>
        </div>
      </div>

      {/* segment-specific card */}
      {segment === 'commune' && (
        <div className="rounded-2xl border p-5" style={{ borderColor: C.border, background: C.bgAlt }}>
          <h3 className="text-[17px] font-normal mb-1" style={{ fontFamily: FONT_HEADING, color: C.text }}>
            Votre commune
          </h3>
          <p className="text-[13px] mb-4" style={{ color: C.textLight }}>
            Ces informations permettront de filtrer les aides disponibles
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2 relative space-y-1">
              <Label htmlFor="communeNom" className="text-[13px] font-medium" style={{ color: C.text }}>Nom de la commune *</Label>
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
                className={inputCls}
              />
              {communeSuggestions.length > 0 && (
                <ul className="absolute z-50 mt-1 w-full border rounded-md shadow-lg max-h-56 overflow-auto" style={{ background: C.bgAlt, borderColor: C.border }}>
                  {communeSuggestions.map((c) => (
                    <li
                      key={c.codeInsee}
                      className="px-4 py-3 text-[14px] cursor-pointer flex justify-between transition-colors hover:bg-muted"
                      style={{ color: C.text }}
                      onMouseDown={() => selectCommune(c)}
                    >
                      <span className="font-medium">{c.nom}</span>
                      <span className="text-[13px]" style={{ color: C.textLight }}>{c.departement} ({c.codeDepartement})</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="sm:col-span-2 space-y-1">
              <Label htmlFor="communeFonction" className="text-[13px] font-medium" style={{ color: C.text }}>Votre fonction</Label>
              <Select value={form.communeFonction} onValueChange={(v) => update({ communeFonction: v })}>
                <SelectTrigger id="communeFonction" className={inputCls}>
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
          </div>
        </div>
      )}

      {segment === 'prive' && (
        <div className="rounded-2xl border p-5" style={{ borderColor: C.border, background: C.bgAlt }}>
          <h3 className="text-[17px] font-normal mb-1" style={{ fontFamily: FONT_HEADING, color: C.text }}>
            Votre situation
          </h3>
          <p className="text-[13px] mb-4" style={{ color: C.textLight }}>
            Ces informations permettront d'identifier les aides pertinentes
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="typeProprietaire" className="text-[13px] font-medium" style={{ color: C.text }}>Type de propriétaire *</Label>
              <Select value={form.typeProprietaire} onValueChange={(v) => update({ typeProprietaire: v })}>
                <SelectTrigger id="typeProprietaire" className={inputCls}>
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
            <div className="space-y-1">
              <Label htmlFor="regimeFiscal" className="text-[13px] font-medium" style={{ color: C.text }}>Régime fiscal</Label>
              <Select value={form.regimeFiscal} onValueChange={(v) => update({ regimeFiscal: v })}>
                <SelectTrigger id="regimeFiscal" className={inputCls}>
                  <SelectValue placeholder="Sélectionner..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="monuments_historiques">Régime Monuments Historiques</SelectItem>
                  <SelectItem value="droit_commun">Droit commun</SelectItem>
                  <SelectItem value="mecenat">Mécénat</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      )}

      {segment === 'btp' && (
        <div className="rounded-2xl border p-5" style={{ borderColor: C.border, background: C.bgAlt }}>
          <h3 className="text-[17px] font-normal mb-4" style={{ fontFamily: FONT_HEADING, color: C.text }}>
            Votre entreprise
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2 space-y-1">
              <Label htmlFor="raisonSociale" className="text-[13px] font-medium" style={{ color: C.text }}>Raison sociale *</Label>
              <Input id="raisonSociale" value={form.raisonSociale} onChange={(e) => update({ raisonSociale: e.target.value })} placeholder="Entreprise Patrimoine SARL" className={inputCls} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="siret" className="text-[13px] font-medium" style={{ color: C.text }}>SIRET</Label>
              <Input id="siret" value={form.siret} onChange={(e) => update({ siret: e.target.value })} placeholder="12345678900014" className={inputCls} />
            </div>
          </div>
        </div>
      )}

      {segment === 'collaborateur' && (
        <div className="rounded-2xl border p-5" style={{ borderColor: C.border, background: C.bgAlt }}>
          <h3 className="text-[17px] font-normal mb-1" style={{ fontFamily: FONT_HEADING, color: C.text }}>
            Votre rôle
          </h3>
          <p className="text-[13px] mb-4" style={{ color: C.textLight }}>
            Pour que la personne qui vous a invité sache qui vous êtes
          </p>
          <div className="space-y-1">
            <Label htmlFor="metier" className="text-[13px] font-medium" style={{ color: C.text }}>Votre rôle sur le projet *</Label>
            <MetierSelect value={form.metier} onChange={(v) => update({ metier: v })} className={inputCls} />
          </div>
          <p className="text-[13px] mt-4" style={{ color: C.textMuted }}>
            Après la création de votre compte, ouvrez le lien d'invitation reçu par e-mail
            pour accéder au projet. Vous le retrouverez ensuite dans l'onglet « Projets ».
          </p>
        </div>
      )}

      {/* navigation buttons */}
      <div className="flex items-center justify-between pt-1">
        <button
          onClick={() => navigate('/onboarding')}
          className="flex items-center gap-2 px-4 py-2.5 text-[13px] font-medium border transition-all duration-300 hover:bg-muted"
          style={{ borderColor: C.border, color: C.textMuted }}
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Retour
        </button>
        <button
          onClick={handleSubmit}
          disabled={!isValid || loading}
          className="group flex items-center gap-2 rounded-lg px-6 py-2.5 text-[13px] font-semibold text-white transition-opacity duration-200 disabled:opacity-50 hover:opacity-90"
          style={{ background: C.terra }}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : (
            <>
              Continuer
              <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
