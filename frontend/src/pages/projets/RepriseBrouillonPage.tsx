import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import i18n from '@/i18n';
import { WizardShell } from '@/components/project/wizard/WizardShell';
import { DiagnosticLoader } from '@/components/project/wizard/DiagnosticLoader';
import { PROJET_WIZARD_STEPS_INVITE } from '@/components/project/wizard/etapes';
import { IconAttention, IconRafraichir } from '@/components/icons';
import { useBrouillonInviteStore } from '@/stores/useBrouillonInviteStore';
import {
  brouillonPretPourRejeu,
  finaliserBrouillon,
  monumentDepuisBrouillon,
} from '@/lib/brouillon-invite';
import { ApiError } from '@/lib/api-error';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';

/** Ce qui a échoué, et ce qu'on en dit. `null` = tout va bien. */
type Echec =
  | { genre: 'offre' }
  | { genre: 'perime' }
  | { genre: 'autre'; message: string }
  | null;

function messageDepuis(err: unknown): Echec {
  if (err instanceof ApiError) {
    // 402 : l'offre du compte ne permet pas ce monument (le gratuit en couvre
    // un seul). Ce n'est pas une panne, c'est une porte — et le brouillon est
    // conservé, pour que rien ne soit perdu si l'offre change.
    if (err.status === 402) return { genre: 'offre' };
    // 422 : le serveur a refusé la forme de ce qu'on lui envoie. Le brouillon
    // date d'une version antérieure du schéma ; le rejouer échouera toujours.
    if (err.status === 422) return { genre: 'perime' };
    return { genre: 'autre', message: err.message };
  }
  return {
    genre: 'autre',
    message: err instanceof Error ? err.message : i18n.t('projets:RepriseBrouillonPage.erreurGenerique'),
  };
}

/** Carte d'échec : un titre, une explication, une ou deux issues. */
function CarteEchec({
  titre,
  description,
  children,
}: {
  titre: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="flex flex-col items-start gap-4 rounded-2xl border p-6"
      style={{ borderColor: C.border, background: C.card }}
    >
      <span
        className="flex h-11 w-11 items-center justify-center rounded-xl"
        style={{ background: 'var(--destructive-muted)', color: 'var(--destructive)' }}
      >
        <IconAttention className="h-5 w-5" />
      </span>
      <div>
        <p className="text-[18px] leading-snug" style={{ fontFamily: SERIF, color: C.ink }}>
          {titre}
        </p>
        <p className="mt-1.5 text-[16px] leading-relaxed" style={{ color: C.grayFg }}>
          {description}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </div>
  );
}

const BOUTON_PLEIN =
  'inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-[16px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)]';
const LIEN_DISCRET = 'text-[16px] font-medium underline underline-offset-2';

/**
 * Rejeu du brouillon découverte : le monument et le projet sont créés pour de
 * vrai, puis on atterrit sur la page du projet.
 *
 * Écran UNIQUE où convergent les trois entrées — inscription email depuis le
 * wizard, retour Google, connexion « J'ai déjà un compte ». C'est ce qui
 * dispense le wizard de survivre au changement d'état d'authentification :
 * lui-même est démonté, et cet écran-ci ne fait qu'une chose.
 *
 * Protégé par la route (`ProtectedRoute`) : il écrit au nom du compte. Plein
 * écran et sans bouton Quitter pendant l'écriture, comme le calcul du
 * diagnostic : une navigation concurrente laisserait un monument sans projet.
 */
export function RepriseBrouillonPage() {
  const { t } = useTranslation(['projets', 'common']);
  const navigate = useNavigate();
  const monumentBrouillon = useBrouillonInviteStore((s) => s.monument);
  const vider = useBrouillonInviteStore((s) => s.vider);
  const [echec, setEchec] = useState<Echec>(null);
  const [essai, setEssai] = useState(0);
  // Décidé UNE FOIS au montage, et c'est indispensable : le rejeu VIDE le
  // brouillon avant même que la navigation vers la page du projet n'ait lieu.
  // Relire `brouillonPretPourRejeu()` à chaque rendu ferait alors gagner la
  // redirection de garde ci-dessous, et l'utilisateur atterrirait sur sa liste
  // de monuments au lieu de son diagnostic.
  const [aRejouer] = useState(brouillonPretPourRejeu);
  // Garde StrictMode : en développement l'effet tourne deux fois, et deux
  // rejeux simultanés créeraient deux monuments.
  const lance = useRef(false);

  useEffect(() => {
    if (lance.current || !aRejouer) return;
    lance.current = true;
    setEchec(null);

    finaliserBrouillon()
      .then(({ projetId }) => navigate(ROUTES.PROJET_DETAIL(projetId), { replace: true }))
      .catch((err: unknown) => {
        const resultat = messageDepuis(err);
        // Un brouillon périmé ne se rejouera jamais : on le jette plutôt que
        // de laisser l'utilisateur buter dessus à chaque connexion.
        if (resultat?.genre === 'perime') vider();
        setEchec(resultat);
        // Rouvre la porte à « Réessayer » : les ids déjà posés font que seule
        // l'étape manquante sera rejouée.
        lance.current = false;
      });
  }, [navigate, vider, essai, aRejouer]);

  // Rien à reprendre (arrivée directe, brouillon déjà consommé) : l'espace.
  if (!aRejouer) {
    return <Navigate to={ROUTES.MONUMENTS} replace />;
  }

  return (
    <WizardShell
      steps={PROJET_WIZARD_STEPS_INVITE}
      step="diagnostic"
      monument={monumentBrouillon ? monumentDepuisBrouillon(monumentBrouillon) : null}
      confirmQuit={false}
      quitDisabled
      exitTo={ROUTES.MONUMENTS}
      // L'attente et les échecs gardent leur dessin : la maquette ne les couvre pas.
      sceneLibre
    >
      {echec === null ? (
        <DiagnosticLoader />
      ) : echec.genre === 'offre' ? (
        <CarteEchec
          titre={t('RepriseBrouillonPage.offre.titre')}
          description={t('RepriseBrouillonPage.offre.description')}
        >
          <Link to={ROUTES.TARIFS()} className={BOUTON_PLEIN} style={{ background: C.orange }}>
            {t('RepriseBrouillonPage.offre.decouvrir')}
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link to={ROUTES.MONUMENTS} className={LIEN_DISCRET} style={{ color: C.blue }}>
            {t('communs.voirMesMonuments')}
          </Link>
        </CarteEchec>
      ) : echec.genre === 'perime' ? (
        <CarteEchec
          titre={t('RepriseBrouillonPage.perime.titre')}
          description={t('RepriseBrouillonPage.perime.description')}
        >
          <Link
            to={ROUTES.MONUMENT_NEW}
            className={BOUTON_PLEIN}
            style={{ background: C.orange }}
          >
            {t('RepriseBrouillonPage.perime.decrire')}
            <ArrowRight className="h-4 w-4" />
          </Link>
        </CarteEchec>
      ) : (
        <CarteEchec
          titre={t('RepriseBrouillonPage.autre.titre')}
          description={t('RepriseBrouillonPage.autre.description', { message: echec.message })}
        >
          <button
            type="button"
            onClick={() => setEssai((n) => n + 1)}
            className={BOUTON_PLEIN}
            style={{ background: C.orange }}
          >
            <IconRafraichir className="h-4 w-4" />
            {t('common:actions.reessayer')}
          </button>
          <Link to={ROUTES.MONUMENTS} className={LIEN_DISCRET} style={{ color: C.blue }}>
            {t('communs.voirMesMonuments')}
          </Link>
        </CarteEchec>
      )}
    </WizardShell>
  );
}
