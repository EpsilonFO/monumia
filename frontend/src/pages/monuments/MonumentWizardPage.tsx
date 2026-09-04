import { useState } from 'react';
import { useNavigate } from 'react-router';
import { ArrowRight, X } from 'lucide-react';
import { MerimeeSearch } from '@/components/monument/MerimeeSearch';
import { MonumentForm } from '@/components/monument/MonumentForm';
import { LogoMonumia } from '@/components/icons';
import { PaywallDialog } from '@/components/shared/Paywall';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useBrouillonInviteStore } from '@/stores/useBrouillonInviteStore';
import { monumentService } from '@/services/monument.service';
import { merimeeService } from '@/services/merimee.service';
import { aideService } from '@/services/aide.service';
import { ApiError } from '@/lib/api-error';
import { REGIONS } from '@/constants/regions';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { toast } from 'sonner';
import type { MerimeeRecord, Monument, MonumentInput, ProtectionLevel, Region } from '@/types';

const REGION_LABEL_TO_VALUE: Record<string, string> = Object.fromEntries(
  REGIONS.map((r) => [r.label.toLowerCase(), r.value])
);

const EYEBROW = 'Nouveau monument';

/**
 * Création d'un MONUMENT : sa fiche, état sanitaire inclus (étape 3 du
 * formulaire). Rien du chantier ici — les travaux, les intentions et le
 * questionnaire appartiennent au projet et se saisissent dans le wizard
 * projet, une fois le monument décrit.
 *
 * Page PUBLIQUE, et c'est le pivot du parcours découverte : un visiteur y
 * décrit son bien sans compte, le brouillon partant dans le `localStorage`
 * (cf. `useBrouillonInviteStore`) plutôt qu'en base. Un connecté, lui, crée
 * son monument pour de vrai. Le critère est `user && token`, exactement celui
 * de `ProtectedRoute` : `App.tsx` attend le rafraîchissement de session avant
 * de rendre le router, donc un profil persisté dont le refresh échoue compte
 * bien comme un visiteur.
 *
 * Sortie : le wizard projet. Dans les deux cas — un monument sans chantier ne
 * mène à aucun diagnostic, et faire atterrir sur la fiche laissait
 * l'utilisateur devant un onglet vide à re-cliquer.
 */
export function MonumentWizardPage() {
  const navigate = useNavigate();
  const connecte = useAuthStore((s) => Boolean(s.user && s.token));
  const addMonument = useMonumentStore((s) => s.addMonument);
  const setActiveMonument = useMonumentStore((s) => s.setActiveMonument);
  const brouillonMonument = useBrouillonInviteStore((s) => s.monument);
  const setBrouillonMonument = useBrouillonInviteStore((s) => s.setMonument);

  // Un visiteur qui revient (F5, onglet fermé, « Précédent » depuis le wizard
  // projet) retrouve sa fiche : mode manuel, formulaire prérempli. La valeur
  // est lue une fois, à l'initialisation — le formulaire est ensuite maître
  // de son propre état.
  const [mode, setMode] = useState<'search' | 'manual'>(brouillonMonument ? 'manual' : 'search');
  const [prefillData, setPrefillData] = useState<Partial<Monument> | null>(
    brouillonMonument ?? null,
  );
  const [saving, setSaving] = useState(false);
  const [paywallOuvert, setPaywallOuvert] = useState(false);

  const handleMerimeeSelect = async (searchRecord: MerimeeRecord) => {
    try {
      const fullRecord = await merimeeService.getByReference(searchRecord.reference);
      const record = fullRecord ?? searchRecord;
      const lastOf = (s: string | undefined) => s?.split(';').pop()?.trim() ?? '';

      const typoEntries = (record.typologie_de_la_protection ?? '')
        .split(';')
        .map((s) => s.toLowerCase().trim());
      let protection: ProtectionLevel = 'non_protege';
      for (const t of typoEntries) {
        if (t.includes('classé')) protection = 'classe';
        else if (t.includes('inscrit')) protection = 'inscrit';
      }

      const regionValue = REGION_LABEL_TO_VALUE[record.region?.toLowerCase() ?? ''] ?? '';
      const titre = record.titre_editorial_de_la_notice ?? '';

      const PROPRIETAIRE_MAP: Record<string, Monument['proprietaire']> = {
        commune: 'public_commune',
        communal: 'public_commune',
        'département': 'public_departement',
        departemental: 'public_departement',
        'région': 'public_region',
        regional: 'public_region',
        'état': 'public_etat',
        etat: 'public_etat',
        'propriété privée': 'prive_personne_physique',
        'privé': 'prive_personne_physique',
        prive: 'prive_personne_physique',
        sci: 'prive_sci',
        association: 'association',
        mixte: 'mixte',
      };
      const statutRaw = record.statut_juridique_de_l_edifice?.toLowerCase().trim() ?? '';
      const proprietaireGuess =
        PROPRIETAIRE_MAP[statutRaw] ??
        Object.entries(PROPRIETAIRE_MAP).find(([k]) => statutRaw.includes(k))?.[1] ??
        undefined;

      let dateProtection: string | undefined;
      const lastDateEntry = lastOf(record.date_et_typologie_de_la_protection);
      if (lastDateEntry) {
        const datePart = lastDateEntry.split(':')[0]?.trim() ?? '';
        if (/^\d{4}\/\d{2}\/\d{2}$/.test(datePart)) {
          dateProtection = datePart.replace(/\//g, '-');
        }
      }
      const typeProtection =
        lastOf(record.date_et_typologie_de_la_protection) ||
        lastOf(record.typologie_de_la_protection) ||
        undefined;

      // Matériaux et type de couverture ne sont plus préremplis : leurs
      // colonnes ont été droppées (migration 20260516174303) et aucune aide ne
      // les lit. Les extraire de Mérimée ne remplissait plus rien.
      setPrefillData({
        nom: titre,
        referenceMerimee: record.reference,
        commune: record.commune_actuelle || record.commune_forme_index,
        codeInsee: record.cog_insee_lors_de_la_protection || undefined,
        departement: record.departement_en_lettres,
        region: regionValue as Region,
        protection,
        dateProtection,
        typeProtection,
        siecleConstruction:
          record.format_abrege_du_siecle_de_construction ||
          record.siecle_de_la_campagne_principale_de_construction ||
          undefined,
        proprietaire: proprietaireGuess,
        descriptionGenerale: record.precision_de_la_protection || undefined,
      });
      setMode('manual');
    } catch (err) {
      toast.error(
        err instanceof Error
          ? err.message
          : 'Erreur lors de la récupération de la fiche Mérimée'
      );
    }
  };

  const handleFormSubmit = async (data: Partial<Monument>) => {
    const payload: MonumentInput = {
      nom: data.nom ?? 'Mon monument',
      commune: data.commune ?? '',
      codeInsee: data.codeInsee ?? '',
      protection: data.protection ?? 'non_protege',
      // Le formulaire impose le type de propriétaire (champ requis) : ce
      // repli ne sert qu'à satisfaire le type.
      proprietaire: data.proprietaire ?? 'prive_personne_physique',
      referenceMerimee: data.referenceMerimee,
      dateProtection: data.dateProtection,
      typeProtection: data.typeProtection,
      siecleConstruction: data.siecleConstruction,
      descriptionGenerale: data.descriptionGenerale,
      etatConservation: data.etatConservation,
    };

    setSaving(true);
    try {
      if (!connecte) {
        // Dry-run du diagnostic invité : rien ne s'enregistre, mais la commune
        // est RÉSOLUE côté serveur (400 si elle est introuvable). La valider
        // maintenant est le seul moment utile — plus tard, le 400 tomberait au
        // rejeu, après l'inscription, sur un brouillon qu'on ne peut plus
        // corriger.
        await aideService.runDiagnosticInvite({
          monument: payload,
          travauxEnvisages: [],
          answers: {},
        });
        setBrouillonMonument(payload);
        navigate(ROUTES.PROJET_NEW_INVITE);
        return;
      }

      const created = await monumentService.create(payload);
      addMonument(created);
      setActiveMonument(created.id);
      navigate(ROUTES.PROJET_NEW(created.id));
    } catch (err) {
      // 402 : le compte a déjà son monument gratuit. Désormais atteignable
      // depuis la landing (les CTA mènent ici sans savoir qui est connecté),
      // donc traité comme une porte et non comme une panne.
      if (err instanceof ApiError && err.status === 402) {
        setPaywallOuvert(true);
      } else {
        toast.error(
          err instanceof Error ? err.message : 'Erreur lors de la création du monument'
        );
      }
    } finally {
      setSaving(false);
    }
  };

  // Quitter : vers l'espace pour un connecté, vers la connexion pour un
  // visiteur (il n'a pas d'espace, et son brouillon l'attend ici).
  const quitterVers = connecte ? ROUTES.MONUMENTS : '/login';

  return (
    <div className="flex h-dvh flex-col overflow-hidden" style={{ background: 'var(--app-bg)' }}>
      <header className="flex shrink-0 items-center justify-between px-5 py-4">
        <button
          type="button"
          onClick={() => navigate(quitterVers)}
          className="flex items-center gap-2.5"
          aria-label="Quitter"
        >
          <LogoMonumia className="h-8 w-8" />
          <span
            className="text-[18px] font-bold tracking-[-0.01em]"
            style={{ fontFamily: SERIF, color: C.ink }}
          >
            Monumia
          </span>
        </button>
        <button
          type="button"
          onClick={() => navigate(quitterVers)}
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors hover:bg-black/5"
          style={{ color: C.grayFg }}
        >
          <X className="h-4 w-4" />
          Quitter
        </button>
      </header>

      {/* Écran unique, sans rail : la colonne est centrée horizontalement et
          calée en HAUT. Le centrage vertical d'avant recalculait la position à
          chaque changement de hauteur : passer d'une étape à l'autre faisait
          glisser tout le bloc, boutons compris. */}
      <main className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="mx-auto w-full max-w-[760px] space-y-4 px-5 py-6 sm:py-8">
          <div className="space-y-1.5 text-center">
            <div
              className="text-[12px] font-semibold uppercase tracking-[0.2em]"
              style={{ color: C.orange }}
            >
              {EYEBROW}
            </div>
            <h1
              className="text-[clamp(1.5rem,3.2vw,2rem)] leading-tight"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              Trouvez votre monument
            </h1>
          </div>

          {mode === 'search' ? (
            <div className="space-y-4">
              <div
                className="rounded-2xl border p-5 sm:p-6"
                style={{
                  borderColor: C.border,
                  background: 'linear-gradient(135deg, var(--secondary) 0%, var(--card) 48%)',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <p className="mb-4 text-[14px]" style={{ color: C.grayFg }}>
                  Cherchez-le dans la base Mérimée&nbsp;: sa fiche sera pré-remplie
                  automatiquement.
                </p>
                <MerimeeSearch onSelect={handleMerimeeSelect} />
              </div>

              <button
                type="button"
                onClick={() => {
                  setPrefillData(null);
                  setMode('manual');
                }}
                className="group flex w-full items-center justify-between rounded-2xl border border-dashed px-6 py-4 text-left transition-colors hover:border-warning hover:bg-warning-muted"
                style={{ borderColor: C.border }}
              >
                <span>
                  <span className="block text-[15px] font-semibold" style={{ color: C.ink }}>
                    Mon monument n&rsquo;est pas dans la liste
                  </span>
                  <span className="mt-0.5 block text-[13px]" style={{ color: C.grayFg }}>
                    Décrivez-le vous-même en quelques champs simples.
                  </span>
                </span>
                <ArrowRight
                  className="h-5 w-5 shrink-0 transition-transform group-hover:translate-x-1"
                  style={{ color: C.orange }}
                />
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              <button
                type="button"
                onClick={() => setMode('search')}
                className="text-[13px] underline-offset-2 hover:underline"
                style={{ color: C.grayMuted }}
              >
                ← Revenir à la recherche
              </button>
              <MonumentForm
                initialData={prefillData ?? undefined}
                onSubmit={handleFormSubmit}
                saving={saving}
              />
            </div>
          )}
        </div>
      </main>

      {/* Le compte a déjà son monument gratuit. En MODALE et non en toast :
          c'est une porte, et on referme sur son formulaire intact plutôt que
          d'être expédié sur la page des tarifs. */}
      <PaywallDialog
        open={paywallOuvert}
        onOpenChange={setPaywallOuvert}
        offre="Multi-monuments"
        titre="Un deuxième monument, et tous les suivants"
        description="L'offre gratuite couvre un monument. Multi-monuments lève la limite, réunit tous vos biens sur un tableau de bord et ouvre les suppressions."
      />
    </div>
  );
}
