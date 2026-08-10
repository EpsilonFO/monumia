import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { ArrowLeft, ArrowRight, Check, Loader2 } from 'lucide-react';
import {
  IconAide,
  IconConseil,
  IconDossier,
  IconSucces,
  IconTemps,
  IconVerrou,
  IconProtection,
} from '@/components/icons';
import { useAuthStore } from '@/stores/useAuthStore';
import { useBillingStore } from '@/stores/useBillingStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { billingService } from '@/services/billing.service';
import { ApiError } from '@/lib/api-error';
import { C, SERIF } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { toast } from 'sonner';
import type { BillingPlan, BillingPrice } from '@/types';

/**
 * Page Tarifs — reprend la mise en page de la section « Tarifs » de la landing
 * (trois portes : gratuit, à l'unité, abonnement) transposée sur les tokens de
 * thème de l'application, pour que le passage du site vitrine à l'app ne se
 * voie pas.
 *
 * Les montants ne sont PAS écrits ici : ils viennent de Stripe via
 * /billing/plans. Un prix affiché qui diffère du prix débité est le pire défaut
 * possible sur une page de paiement, et c'est le sort réservé à tout montant
 * recopié à la main.
 */

const CURRENCY = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

function formatPrice(price: BillingPrice | undefined): string | null {
  if (!price || price.amountCents == null) return null;
  return CURRENCY.format(price.amountCents / 100);
}

const DECOUVERTE_FEATURES = [
  'Description guidée de votre lieu et de votre projet',
  'Recherche parmi toutes les aides recensées',
  'Estimation du montant que votre projet peut espérer',
  'Vos chances d’obtenir ces aides, critère par critère',
];

const DOSSIER_FEATURES = [
  'Le nom de chaque aide, son organisme et ses contacts',
  'Les dates clés du projet et le calendrier des sessions',
  'La checklist des pièces demandées par les financeurs',
  'Un espace partagé avec votre architecte ou vos artisans',
  'Le dossier complet à télécharger, prêt à transmettre',
];

const ABONNEMENT_FEATURES = [
  'Tous vos projets débloqués, présents et à venir',
  'La veille des aides : nouvelles aides, appels à projets',
  'Les alertes avant chaque date limite',
  'Le tableau de bord et le suivi de toutes vos demandes',
  'La recherche libre des mécènes et fondations',
];

export function TarifsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const token = useAuthStore((s) => s.token);
  const access = useBillingStore((s) => s.access);
  const loadAccess = useBillingStore((s) => s.loadAccess);

  // Projet d'où l'on vient : porté par l'URL et non par le state de navigation,
  // car l'aller-retour vers Stripe quitte le site et perd tout state React.
  const monumentId = searchParams.get('projet') ?? undefined;
  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === monumentId));
  const paymentStatus = searchParams.get('paiement');

  const [plans, setPlans] = useState<BillingPrice[]>([]);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [pending, setPending] = useState<BillingPlan | 'portal' | null>(null);
  // « attente » = le webhook n'était pas encore arrivé au bout du délai. Il
  // FAUT distinguer ce cas d'une confirmation : annoncer « c'est débloqué »
  // quand l'accès n'est pas accordé est un mensonge que l'utilisateur constate
  // à l'écran suivant.
  const [confirmState, setConfirmState] = useState<'confirmation' | 'confirme' | 'attente'>(
    'confirmation'
  );

  useEffect(() => {
    billingService
      .getPlans()
      .then((res) => {
        setPlans(res.plans);
        setConfigured(res.configured);
      })
      .catch(() => setConfigured(false));
  }, []);

  const dossierPrice = plans.find((p) => p.plan === 'dossier');
  const abonnementPrice = plans.find((p) => p.plan === 'abonnement');

  const subscribed = !!access?.subscription;
  const projectUnlocked =
    !!access && (access.allAccess || (!!monumentId && access.unlockedMonumentIds.includes(monumentId)));
  // A payé au moins une fois → possède un Customer Stripe, donc un portail.
  const hasPaid = subscribed || (access?.unlockedMonumentIds.length ?? 0) > 0;

  // Retour de Stripe : le webhook peut n'être pas encore arrivé quand le
  // navigateur, lui, est déjà revenu. On réinterroge les droits quelques
  // secondes plutôt que d'annoncer un échec sur une simple course de vitesse.
  const confirmTimer = useRef<number | null>(null);
  useEffect(() => {
    if (paymentStatus !== 'succes') return;
    let cancelled = false;
    let attempts = 0;
    const poll = async () => {
      await loadAccess();
      if (cancelled) return;
      const current = useBillingStore.getState().access;
      const done =
        !!current &&
        (current.allAccess ||
          (!!monumentId && current.unlockedMonumentIds.includes(monumentId)) ||
          !!current.subscription);
      if (done) {
        setConfirmState('confirme');
        return;
      }
      if (attempts >= 5) {
        setConfirmState('attente');
        return;
      }
      attempts += 1;
      confirmTimer.current = window.setTimeout(poll, 1500);
    };
    poll();
    return () => {
      cancelled = true;
      if (confirmTimer.current) window.clearTimeout(confirmTimer.current);
    };
  }, [paymentStatus, monumentId, loadAccess]);

  const startCheckout = useCallback(
    async (plan: BillingPlan) => {
      if (!token) {
        navigate('/login', { state: { from: ROUTES.TARIFS(monumentId) } });
        return;
      }
      setPending(plan);
      try {
        // Redirection plein page (et non un onglet) : Stripe Checkout héberge le
        // formulaire de carte, et les URL de retour ramènent ici.
        window.location.href = await billingService.startCheckout(plan, monumentId);
      } catch (err) {
        setPending(null);
        toast.error(
          err instanceof ApiError ? err.message : "Impossible d'ouvrir le paiement pour le moment."
        );
      }
    },
    [token, monumentId, navigate]
  );

  const openPortal = useCallback(async () => {
    setPending('portal');
    try {
      window.location.href = await billingService.openPortal();
    } catch (err) {
      setPending(null);
      toast.error(
        err instanceof ApiError ? err.message : 'Portail de facturation indisponible pour le moment.'
      );
    }
  }, []);

  const backTo = monumentId ? ROUTES.PROJET_DETAIL(monumentId) : token ? '/app' : '/login';

  return (
    <div className="min-h-screen bg-app-bg">
      <div className="mx-auto w-full max-w-6xl px-5 py-10 lg:px-8 lg:py-14">
        <Link
          to={backTo}
          className="inline-flex items-center gap-1.5 text-[13px] font-medium transition-opacity hover:opacity-70"
          style={{ color: C.blue }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {monument ? monument.nom : 'Retour'}
        </Link>

        {paymentStatus === 'succes' && (
          <PaymentSuccess
            state={confirmState}
            monumentName={monument?.nom}
            onGoToProject={monumentId ? () => navigate(ROUTES.PROJET_DETAIL(monumentId)) : undefined}
          />
        )}

        {paymentStatus === 'annule' && (
          <div
            className="mt-6 flex items-start gap-3 rounded-xl border p-4"
            style={{ background: C.paleBlue, borderColor: C.border }}
          >
            <IconConseil className="mt-0.5 h-5 w-5 shrink-0" style={{ color: C.blue }} />
            <p className="text-[14px]" style={{ color: C.ink }}>
              Paiement abandonné, rien n’a été débité. Vos aides identifiées vous attendent.
            </p>
          </div>
        )}

        {/* En-tête — kicker, titre serif, filet orange : la signature de section
            reprise de la landing. */}
        <header className="mx-auto mt-8 max-w-3xl text-center">
          <div className="flex items-center justify-center gap-3">
            <span className="h-px w-7" style={{ background: C.orange, opacity: 0.65 }} />
            <span
              className="text-[12.5px] font-semibold uppercase tracking-[0.18em]"
              style={{ color: C.orange }}
            >
              Tarifs
            </span>
            <span className="h-px w-7" style={{ background: C.orange, opacity: 0.65 }} />
          </div>
          <h1
            className="mt-5 text-[clamp(1.8rem,3.2vw,2.3rem)] leading-[1.2] tracking-[-0.01em]"
            style={{ fontFamily: SERIF, color: C.ink }}
          >
            {monument ? (
              <>
                Débloquez les aides de <em className="italic" style={{ color: C.orange }}>{monument.nom}</em>
              </>
            ) : (
              'Payez quand vous êtes prêt, pas avant'
            )}
          </h1>
          <div className="mx-auto mt-5 h-[3px] w-12 rounded-full" style={{ background: C.orange }} />
          <p
            className="mx-auto mt-5 max-w-2xl text-[16.5px] font-medium leading-[1.65]"
            style={{ color: C.grayFg }}
          >
            L’estimation de vos aides est gratuite. Ce qui se paie, c’est le passage à
            l’action : savoir de quelles aides il s’agit, auprès de qui les demander, et avec quelles
            pièces.
          </p>
        </header>

        {configured === false && (
          <div
            className="mx-auto mt-8 max-w-2xl rounded-xl border p-4 text-center"
            style={{ background: C.paleOrange, borderColor: C.orange }}
          >
            <p className="text-[14px] font-medium" style={{ color: C.ink }}>
              Le paiement en ligne ouvre très bientôt. Écrivez-nous en attendant : nous débloquons
              votre projet à la main.
            </p>
          </div>
        )}

        <div className="mt-12 grid items-stretch gap-6 lg:grid-cols-3">
          {/* ── Découverte ─────────────────────────────────────────── */}
          <PlanCard
            icon={IconAide}
            name="Découverte"
            tagline="Pour savoir ce que votre lieu peut espérer."
            price="0 €"
            priceNote="pour toujours"
            features={DECOUVERTE_FEATURES}
            featuresIntro={null}
            accent={C.blue}
            current
            currentLabel="Votre offre actuelle"
          />

          {/* ── Dossier ────────────────────────────────────────────── */}
          <PlanCard
            icon={IconDossier}
            name="Dossier"
            tagline="Pour monter un dossier solide, du premier coup."
            price={formatPrice(dossierPrice) ?? 'Bientôt'}
            priceNote="paiement unique, pour un projet"
            features={DOSSIER_FEATURES}
            featuresIntro="Tout Découverte, plus :"
            accent={C.orange}
            highlight
            badge={monument ? 'Pour ce projet' : 'Le plus choisi'}
            current={projectUnlocked}
            currentLabel={
              subscribed
                ? 'Inclus dans votre abonnement'
                : monument
                  ? 'Ce projet est débloqué'
                  : 'Déjà débloqué'
            }
            cta={{
              label: monument ? `Débloquer ${monument.nom}` : 'Débloquer un projet',
              onClick: () => startCheckout('dossier'),
              // Sans projet en contexte, on ne saurait pas quoi débloquer :
              // l'utilisateur est renvoyé vers la liste de ses projets.
              redirectTo: monumentId ? undefined : ROUTES.PROJETS,
              redirectLabel: 'Choisir un projet',
            }}
            loading={pending === 'dossier'}
            waiting={configured === null}
            unavailable={configured === false || (configured === true && !dossierPrice)}
          />

          {/* ── Abonnement ─────────────────────────────────────────── */}
          <PlanCard
            icon={IconProtection}
            name="Abonnement"
            tagline="Pour piloter votre patrimoine dans la durée."
            price={formatPrice(abonnementPrice) ?? 'Bientôt'}
            priceNote={abonnementPrice?.recurring ? 'par mois, sans engagement' : 'par mois'}
            features={ABONNEMENT_FEATURES}
            featuresIntro="Tout Dossier, plus :"
            accent={C.orangeVif}
            dark
            current={subscribed}
            currentLabel="Votre abonnement est actif"
            cta={
              subscribed
                ? { label: 'Gérer mon abonnement', onClick: openPortal }
                : { label: 'Choisir l’abonnement', onClick: () => startCheckout('abonnement') }
            }
            loading={pending === 'abonnement' || pending === 'portal'}
            waiting={configured === null}
            // Un abonné garde son bouton « Gérer mon abonnement » : il mène au
            // portail Stripe, qui ne dépend pas des prix configurés.
            unavailable={!subscribed && (configured === false || !abonnementPrice)}
          />
        </div>

        {/* Le portail Stripe n'est proposé qu'aux comptes qui ont réellement
            payé : sans Customer côté Stripe, l'ouverture échouerait. */}
        <Reassurance
          subscription={access?.subscription ?? null}
          onOpenPortal={hasPaid ? openPortal : undefined}
        />
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────
   Carte d'offre
   ──────────────────────────────────────────── */

interface PlanCardProps {
  icon: typeof IconAide;
  name: string;
  tagline: string;
  price: string;
  priceNote: string;
  features: string[];
  featuresIntro: string | null;
  accent: string;
  /** Carte du milieu : bordure accentuée et ombre portée. */
  highlight?: boolean;
  /** Carte pleine (fond bleu profond), pour l'offre la plus complète. */
  dark?: boolean;
  badge?: string;
  current?: boolean;
  currentLabel?: string;
  cta?: {
    label: string;
    onClick: () => void;
    /** Quand l'action réclame d'abord de choisir un projet. */
    redirectTo?: string;
    redirectLabel?: string;
  };
  loading?: boolean;
  /** Les tarifs ne sont pas encore revenus du serveur. */
  waiting?: boolean;
  /**
   * Offre pas encore vendable (Stripe non branché, ou prix manquant). Le bouton
   * le DIT au lieu de rester grisé sous son libellé habituel : un « Débloquer
   * Château » inerte laisse croire à une panne.
   */
  unavailable?: boolean;
}

const UNAVAILABLE_HINT =
  "Le paiement en ligne n'est pas encore activé. Écrivez-nous : nous débloquons votre projet à la main.";

function PlanCard({
  icon: Icon,
  name,
  tagline,
  price,
  priceNote,
  features,
  featuresIntro,
  accent,
  highlight = false,
  dark = false,
  badge,
  current = false,
  currentLabel,
  cta,
  loading = false,
  waiting = false,
  unavailable = false,
}: PlanCardProps) {
  const shell = dark
    ? 'relative flex h-full flex-col overflow-hidden rounded-2xl p-7 transition-all duration-300 hover:-translate-y-1.5'
    : highlight
      ? 'relative flex h-full flex-col rounded-2xl border-[1.5px] p-7 transition-all duration-300 hover:-translate-y-2'
      : 'relative flex h-full flex-col rounded-2xl border p-7 transition-all duration-300 hover:-translate-y-1.5';

  const shellStyle = dark
    ? { background: C.blue, boxShadow: 'var(--shadow-pop)' }
    : highlight
      ? { background: C.card, borderColor: accent, boxShadow: 'var(--shadow-pop)' }
      : { background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' };

  const titleColor = dark ? '#fff' : C.ink;
  const bodyColor = dark ? 'rgba(255,255,255,0.72)' : C.grayFg;
  const faintColor = dark ? 'rgba(255,255,255,0.55)' : C.grayMuted;

  return (
    <div className={shell} style={shellStyle}>
      {badge && !current && (
        <span
          className="absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full px-3.5 py-1 text-[11.5px] font-semibold uppercase tracking-[0.08em] text-white"
          style={{ background: accent }}
        >
          {badge}
        </span>
      )}

      <div className="flex items-center gap-3">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
          style={{ background: dark ? 'rgba(255,255,255,0.12)' : C.paleBlue }}
        >
          <Icon className="h-5 w-5" style={{ color: dark ? '#fff' : C.blue }} strokeWidth={1.8} />
        </div>
        <h2 className="text-[1.25rem] font-bold" style={{ fontFamily: SERIF, color: titleColor }}>
          {name}
        </h2>
      </div>
      <p className="mt-2 text-[13.5px] leading-snug" style={{ color: faintColor }}>
        {tagline}
      </p>

      <p
        className="mt-6 text-[2rem] font-bold leading-none tabular-nums"
        style={{ fontFamily: SERIF, color: dark ? '#fff' : C.blue }}
      >
        {price}
      </p>
      <p className="mt-1.5 text-[12.5px]" style={{ color: faintColor }}>
        {priceNote}
      </p>

      {featuresIntro && (
        <p
          className="mt-6 text-[12px] font-semibold uppercase tracking-[0.08em]"
          style={{ color: accent }}
        >
          {featuresIntro}
        </p>
      )}
      <ul className={`${featuresIntro ? 'mt-3' : 'mt-6'} flex-1 space-y-2.5`}>
        {features.map((feature) => (
          <li
            key={feature}
            className="flex items-start gap-2.5 text-[14px] leading-snug"
            style={{ color: bodyColor }}
          >
            <Check className="mt-0.5 h-4 w-4 shrink-0" style={{ color: accent }} strokeWidth={2.4} />
            {feature}
          </li>
        ))}
      </ul>

      <div className="mt-7">
        {current ? (
          <div
            className="flex items-center justify-center gap-2 rounded-full px-5 py-3 text-[14px] font-semibold"
            style={{
              background: dark ? 'rgba(255,255,255,0.14)' : C.successMuted,
              color: dark ? '#fff' : C.success,
            }}
          >
            <IconSucces className="h-4 w-4" />
            {currentLabel ?? 'Offre en cours'}
          </div>
        ) : unavailable ? (
          // Ni bouton ni action : une mention neutre. Le pourquoi est porté une
          // seule fois par le bandeau en tête de page, pas répété par carte.
          <div
            title={UNAVAILABLE_HINT}
            className="flex items-center justify-center gap-2 rounded-full px-5 py-3 text-[14px] font-semibold"
            style={{
              background: dark ? 'rgba(255,255,255,0.10)' : C.paleBlue,
              color: dark ? '#fff' : C.blue,
            }}
          >
            <IconTemps className="h-4 w-4" />
            Bientôt
          </div>
        ) : cta?.redirectTo ? (
          <Link
            to={cta.redirectTo}
            className="group inline-flex w-full items-center justify-center gap-2 rounded-full px-5 py-3 text-[14.5px] font-semibold transition-all duration-300 hover:-translate-y-0.5"
            style={{ background: accent, color: '#fff' }}
          >
            {cta.redirectLabel ?? cta.label}
            <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
          </Link>
        ) : cta ? (
          <button
            type="button"
            onClick={cta.onClick}
            disabled={waiting || loading}
            className="group inline-flex w-full items-center justify-center gap-2 rounded-full px-5 py-3 text-[14.5px] font-semibold transition-all duration-300 hover:-translate-y-0.5 disabled:translate-y-0 disabled:cursor-progress disabled:opacity-55"
            style={
              dark ? { background: '#fff', color: C.blue } : { background: accent, color: '#fff' }
            }
          >
            {loading || waiting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <IconVerrou className="h-4 w-4" />
            )}
            {cta.label}
            {!loading && !waiting && (
              <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
            )}
          </button>
        ) : null}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────
   Retour de paiement
   ──────────────────────────────────────────── */

function PaymentSuccess({
  state,
  monumentName,
  onGoToProject,
}: {
  state: 'confirmation' | 'confirme' | 'attente';
  monumentName?: string;
  onGoToProject?: () => void;
}) {
  const confirme = state === 'confirme';
  // L'attente prend les couleurs de l'information et non du succès : le
  // paiement est passé, l'accès n'est pas encore là, et il ne faut promettre
  // que ce qui est vrai.
  const tone = confirme
    ? { bg: C.successMuted, border: C.success, dot: C.success }
    : { bg: C.paleBlue, border: C.blue, dot: C.blue };

  const titre = {
    confirmation: 'Paiement reçu, activation en cours…',
    confirme: 'C’est débloqué. Merci !',
    attente: 'Paiement reçu. L’activation se termine.',
  }[state];

  const texte = {
    confirmation: 'Quelques secondes le temps que Stripe nous confirme la transaction.',
    confirme: monumentName
      ? `Le détail des aides de ${monumentName} est maintenant visible. Votre facture arrive par e-mail.`
      : 'Le détail de vos aides est maintenant visible. Votre facture arrive par e-mail.',
    attente:
      'La confirmation de Stripe met plus de temps que prévu. Elle arrivera d’elle-même : rechargez cette page dans une minute. Rien ne sera débité deux fois.',
  }[state];

  return (
    <div
      className="mt-6 flex flex-col gap-4 rounded-2xl border p-5 sm:flex-row sm:items-center"
      style={{ background: tone.bg, borderColor: tone.border }}
    >
      <div
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full"
        style={{ background: tone.dot }}
      >
        {state === 'confirmation' ? (
          <Loader2 className="h-5 w-5 animate-spin text-white" />
        ) : confirme ? (
          <IconSucces className="h-6 w-6 text-white" />
        ) : (
          <IconTemps className="h-6 w-6 text-white" />
        )}
      </div>
      <div className="flex-1">
        <h2 className="text-[17px] font-semibold" style={{ fontFamily: SERIF, color: C.ink }}>
          {titre}
        </h2>
        <p className="mt-1 text-[14px]" style={{ color: C.grayFg }}>
          {texte}
        </p>
      </div>
      {confirme && onGoToProject && (
        <button
          type="button"
          onClick={onGoToProject}
          className="group inline-flex shrink-0 items-center justify-center gap-2 rounded-full px-5 py-2.5 text-[14px] font-semibold text-white transition-all duration-300 hover:-translate-y-0.5"
          style={{ background: C.success }}
        >
          Voir mes aides
          <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
        </button>
      )}
    </div>
  );
}

/* ────────────────────────────────────────────
   Bas de page — lever les dernières objections
   ──────────────────────────────────────────── */

function Reassurance({
  subscription,
  onOpenPortal,
}: {
  subscription: { status: string; currentPeriodEnd: string | null; cancelAtPeriodEnd: boolean } | null;
  onOpenPortal?: () => void;
}) {
  const periodEnd = subscription?.currentPeriodEnd
    ? new Date(subscription.currentPeriodEnd).toLocaleDateString('fr-FR', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      })
    : null;

  return (
    <div className="mt-12 space-y-5">
      <div className="flex flex-wrap items-center justify-center gap-x-7 gap-y-3">
        {[
          'Paiement sécurisé par Stripe',
          'Aucune carte enregistrée chez nous',
          'Abonnement résiliable en un clic',
          'Facture envoyée par e-mail',
        ].map((item) => (
          <span
            key={item}
            className="inline-flex items-center gap-2 text-[13px] font-medium"
            style={{ color: C.grayFg }}
          >
            <IconSucces className="h-3.5 w-3.5 shrink-0" style={{ color: C.success }} />
            {item}
          </span>
        ))}
      </div>

      {(subscription || onOpenPortal) && (
        <p className="text-center text-[13px]" style={{ color: C.grayMuted }}>
          {subscription?.cancelAtPeriodEnd && periodEnd
            ? `Votre abonnement prend fin le ${periodEnd}. Vos projets restent débloqués jusque-là.`
            : subscription && periodEnd
              ? `Prochain prélèvement le ${periodEnd}.`
              : null}
          {onOpenPortal && (
            <>
              {subscription && periodEnd ? ' ' : null}
              <button
                type="button"
                onClick={onOpenPortal}
                className="font-semibold underline underline-offset-2 transition-opacity hover:opacity-70"
                style={{ color: C.blue }}
              >
                Voir mes factures
              </button>
            </>
          )}
        </p>
      )}
    </div>
  );
}
