import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { ArrowLeft, ArrowRight, Check, Loader2 } from 'lucide-react';
import {
  IconAide,
  IconConseil,
  IconSucces,
  IconTemps,
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
import type { BillingPlan, BillingSubscription } from '@/types';

/**
 * Les deux offres payantes se négocient : leurs cartes mènent à un courrier,
 * pas à un paiement. Même adresse que le site vitrine, pour que les demandes
 * arrivent au même endroit, et un sujet prérempli par offre pour savoir de
 * quoi on parle avant d'ouvrir le message.
 */
function contactMailto(offre: string): string {
  return `mailto:contact@monumia.fr?subject=${encodeURIComponent(`Offre ${offre}`)}`;
}

/**
 * Page Tarifs — trois portes : Gratuit, Veille, Multi-monuments, transposées
 * sur les tokens de thème de l'application pour que le passage du site vitrine
 * à l'app ne se voie pas.
 *
 * Les deux offres payantes sont des abonnements mensuels, et la seconde
 * contient la première : les listes de bénéfices se lisent donc en cumul
 * (« Tout Veille, plus… »), comme le calcul des droits côté serveur.
 *
 * Aucun montant n'est affiché : les deux offres payantes se négocient, leurs
 * cartes portent « Sur demande » et mènent à un courrier. C'est aussi ce que dit
 * `PLANS_VENDABLES`, vide des deux côtés, et `POST /billing/checkout` refuse en
 * 409 tout ce qui n'y figure pas.
 *
 * Le jour où un prix devient public, il ne sera pas écrit ici : il viendra de
 * Stripe via /billing/plans. Un prix affiché qui diffère du prix débité est le
 * pire défaut possible sur une page de paiement, et c'est le sort réservé à tout
 * montant recopié à la main.
 */

const GRATUIT_FEATURES = [
  'Un monument et jusqu’à deux projets de travaux',
  'La recherche parmi toutes les aides recensées',
  'Le détail de chaque aide : organisme, contacts, pièces demandées',
  'Vos chances de l’obtenir, critère par critère',
];

const VEILLE_FEATURES = [
  'Autant de projets de travaux que nécessaire, sur votre monument',
  'Une équipe : invitez votre architecte, vos artisans, un assistant',
  'Les aides qui ouvrent bientôt, nommées avant tout le monde',
  'L’échéancier du chantier : dates limites d’aides et de dossiers',
  'Un email le jour où un guichet ouvre',
  'Un rappel par email avant chaque date limite',
];

const MULTI_FEATURES = [
  'Autant de monuments que vous en gérez',
  'Le tableau de bord : tous vos biens et leurs échéances d’un coup d’œil',
  'La suppression d’un monument ou d’un projet',
];

export function TarifsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const token = useAuthStore((s) => s.token);
  const access = useBillingStore((s) => s.access);
  const loadAccess = useBillingStore((s) => s.loadAccess);

  // Monument d'où l'on vient : porté par l'URL et non par le state de
  // navigation, car l'aller-retour vers Stripe quitte le site et perd tout
  // state React. Il ne sert plus qu'à revenir au bon endroit — les offres sont
  // désormais des abonnements de compte, elles ne débloquent pas un bien.
  const monumentId = searchParams.get('projet') ?? undefined;
  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === monumentId));
  const paymentStatus = searchParams.get('paiement');

  // Seul le portail Stripe reste une action asynchrone sur cette page : plus
  // rien ne s'achète en ligne.
  const [pending, setPending] = useState<'portal' | null>(null);
  // « attente » = le webhook n'était pas encore arrivé au bout du délai. Il
  // FAUT distinguer ce cas d'une confirmation : annoncer « c'est débloqué »
  // quand l'accès n'est pas accordé est un mensonge que l'utilisateur constate
  // à l'écran suivant.
  const [confirmState, setConfirmState] = useState<'confirmation' | 'confirme' | 'attente'>(
    'confirmation'
  );

  const plansDetenus = access?.plans ?? [];
  const aMultiMonuments = plansDetenus.includes('multi_monuments');
  // Multi-monuments contient Veille : la carte Veille s'affiche alors comme
  // acquise, et non comme un achat possible — la revendre ferait payer deux
  // fois le même service, et le serveur refuse d'ailleurs la session.
  const aVeille = plansDetenus.includes('veille') || aMultiMonuments;
  // Le portail de facturation n'existe que pour un compte rattaché à un
  // Customer Stripe. Détenir une offre ne suffit pas : Multi-monuments se
  // négocie et peut avoir été ouverte sans passer par Stripe.
  const portailDisponible = access?.portail ?? false;

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
      // L'offre attendue est celle que Stripe vient d'encaisser : la lire dans
      // l'URL de retour évite de conclure « c'est bon » sur un abonnement plus
      // ancien qui traînait déjà sur le compte.
      const attendu = searchParams.get('plan');
      const done =
        !!current &&
        current.plans.length > 0 &&
        (!attendu || current.plans.includes(attendu as BillingPlan));
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
  }, [paymentStatus, searchParams, loadAccess]);

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

  const backTo = monumentId ? ROUTES.MONUMENT_DETAIL(monumentId) : token ? '/app' : '/login';

  return (
    <div className="min-h-screen bg-app-bg">
      <div className="mx-auto w-full max-w-6xl px-5 py-10 lg:px-8 lg:py-14">
        <Link
          to={backTo}
          className="inline-flex items-center gap-1.5 text-[15px] font-medium transition-opacity hover:opacity-70"
          style={{ color: C.blue }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {monument ? monument.nom : 'Retour'}
        </Link>

        {paymentStatus === 'succes' && (
          <PaymentSuccess
            state={confirmState}
            monumentName={monument?.nom}
            onGoToProject={monumentId ? () => navigate(ROUTES.MONUMENT_DETAIL(monumentId)) : undefined}
          />
        )}

        {paymentStatus === 'annule' && (
          <div
            className="mt-6 flex items-start gap-3 rounded-xl border p-4"
            style={{ background: C.paleBlue, borderColor: C.border }}
          >
            <IconConseil className="mt-0.5 h-5 w-5 shrink-0" style={{ color: C.blue }} />
            <p className="text-[16px]" style={{ color: C.ink }}>
              Paiement abandonné, rien n’a été débité. Votre offre actuelle est intacte.
            </p>
          </div>
        )}

        {/* En-tête — kicker, titre serif, filet orange : la signature de section
            reprise de la landing. */}
        <header className="mx-auto mt-8 max-w-3xl text-center">
          <div className="flex items-center justify-center gap-3">
            <span className="h-px w-7" style={{ background: C.orange, opacity: 0.65 }} />
            <span
              className="text-[14.5px] font-semibold uppercase tracking-[0.18em]"
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
                Allez plus loin sur <em className="italic" style={{ color: C.orange }}>{monument.nom}</em>
              </>
            ) : (
              'Payez quand vous êtes prêt, pas avant'
            )}
          </h1>
          <div className="mx-auto mt-5 h-[3px] w-12 rounded-full" style={{ background: C.orange }} />
          <p
            className="mx-auto mt-5 max-w-2xl text-[18.5px] font-medium leading-[1.65]"
            style={{ color: C.grayFg }}
          >
            Identifier vos aides et lire leur détail est gratuit, pour toujours. Ce qui se paie,
            c’est le temps : savoir à l’avance quels guichets ouvrent, être prévenu avant chaque
            date limite, et mener autant de chantiers et de monuments qu’il en faut.
          </p>
        </header>

        <div className="mt-12 grid items-stretch gap-6 lg:grid-cols-3">
          {/* ── Gratuit ────────────────────────────────────────────── */}
          <PlanCard
            icon={IconAide}
            name="Gratuit"
            tagline="Pour identifier ce que votre lieu peut espérer."
            price="0 €"
            priceNote="pour toujours"
            features={GRATUIT_FEATURES}
            featuresIntro={null}
            accent={C.blue}
            current={plansDetenus.length === 0}
            currentLabel="Votre offre actuelle"
          />

          {/* ── Veille ─────────────────────────────────────────────── */}
          <PlanCard
            icon={IconTemps}
            name="Veille"
            tagline="Pour ne rater aucun guichet, ni aucune date limite."
            price="Sur demande"
            priceNote="nous en parlons ensemble"
            features={VEILLE_FEATURES}
            featuresIntro="Tout Gratuit, plus :"
            accent={C.orange}
            highlight
            badge="Le plus choisi"
            current={aVeille}
            currentLabel={
              aMultiMonuments ? 'Incluse dans Multi-monuments' : 'Votre abonnement est actif'
            }
            cta={{ label: 'Nous contacter', href: contactMailto('Veille') }}
          />

          {/* ── Multi-monuments ────────────────────────────────────── */}
          <PlanCard
            icon={IconProtection}
            name="Multi-monuments"
            tagline="Pour piloter plusieurs biens dans la durée."
            price="Sur demande"
            priceNote="selon la taille de votre parc"
            features={MULTI_FEATURES}
            featuresIntro="Tout Veille, plus :"
            accent={C.orangeVif}
            dark
            current={aMultiMonuments}
            currentLabel="Votre abonnement est actif"
            cta={
              // Une offre sur mesure se fait suivre par un humain : le portail
              // n'est proposé que s'il existe vraiment pour ce compte.
              aMultiMonuments && portailDisponible
                ? { label: 'Gérer mon abonnement', onClick: openPortal }
                : { label: 'Nous contacter', href: contactMailto('Multi-monuments') }
            }
            loading={pending === 'portal'}
          />
        </div>

        {/* Le portail Stripe n'est proposé qu'aux comptes qui ont réellement
            payé : sans Customer côté Stripe, l'ouverture échouerait. */}
        <Reassurance
          subscription={access?.subscription ?? null}
          onOpenPortal={portailDisponible ? openPortal : undefined}
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
  /**
   * L'action de la carte. `onClick` pour un paiement ou le portail Stripe,
   * `href` pour une offre qui se négocie et mène à un mailto : le bouton est
   * alors un vrai lien, pour que le client puisse l'ouvrir dans son logiciel
   * de courrier comme n'importe quelle adresse.
   */
  cta?: { label: string; onClick: () => void; href?: never }
    | { label: string; href: string; onClick?: never };
  loading?: boolean;
  /** Les tarifs ne sont pas encore revenus du serveur. */
  waiting?: boolean;
}

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
          className="absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full px-3.5 py-1 text-[13.5px] font-semibold uppercase tracking-[0.08em] text-white"
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
      <p className="mt-2 text-[15.5px] leading-snug" style={{ color: faintColor }}>
        {tagline}
      </p>

      <p
        className="mt-6 text-[2rem] font-bold leading-none tabular-nums"
        style={{ fontFamily: SERIF, color: dark ? '#fff' : C.blue }}
      >
        {price}
      </p>
      <p className="mt-1.5 text-[14.5px]" style={{ color: faintColor }}>
        {priceNote}
      </p>

      {featuresIntro && (
        <p
          className="mt-6 text-[14px] font-semibold uppercase tracking-[0.08em]"
          style={{ color: accent }}
        >
          {featuresIntro}
        </p>
      )}
      <ul className={`${featuresIntro ? 'mt-3' : 'mt-6'} flex-1 space-y-2.5`}>
        {features.map((feature) => (
          <li
            key={feature}
            className="flex items-start gap-2.5 text-[16px] leading-snug"
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
            className="flex items-center justify-center gap-2 rounded-full px-5 py-3 text-[16px] font-semibold"
            style={{
              background: dark ? 'rgba(255,255,255,0.14)' : C.successMuted,
              color: dark ? '#fff' : C.success,
            }}
          >
            <IconSucces className="h-4 w-4" />
            {currentLabel ?? 'Offre en cours'}
          </div>
        ) : cta?.href ? (
          // Un vrai lien, pas un bouton : « Nous contacter » ouvre un mailto, et
          // doit se comporter comme une adresse (clic milieu, copier le lien).
          <a
            href={cta.href}
            className="group inline-flex w-full items-center justify-center gap-2 rounded-full px-5 py-3 text-[16.5px] font-semibold transition-all duration-300 hover:-translate-y-0.5"
            style={dark ? { background: '#fff', color: C.blue } : { background: accent, color: '#fff' }}
          >
            {cta.label}
            <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
          </a>
        ) : cta?.onClick ? (
          <button
            type="button"
            onClick={cta.onClick}
            disabled={waiting || loading}
            className="group inline-flex w-full items-center justify-center gap-2 rounded-full px-5 py-3 text-[16.5px] font-semibold transition-all duration-300 hover:-translate-y-0.5 disabled:translate-y-0 disabled:cursor-progress disabled:opacity-55"
            style={
              dark ? { background: '#fff', color: C.blue } : { background: accent, color: '#fff' }
            }
          >
            {(loading || waiting) && <Loader2 className="h-4 w-4 animate-spin" />}
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
    confirme: 'C’est actif. Merci !',
    attente: 'Paiement reçu. L’activation se termine.',
  }[state];

  const texte = {
    confirmation: 'Quelques secondes le temps que Stripe nous confirme la transaction.',
    confirme: monumentName
      ? `Votre offre est active sur ${monumentName} comme sur tous vos biens. Votre facture arrive par e-mail.`
      : 'Votre offre est active. Votre facture arrive par e-mail.',
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
        <h2 className="text-[19px] font-semibold" style={{ fontFamily: SERIF, color: C.ink }}>
          {titre}
        </h2>
        <p className="mt-1 text-[16px]" style={{ color: C.grayFg }}>
          {texte}
        </p>
      </div>
      {confirme && onGoToProject && (
        <button
          type="button"
          onClick={onGoToProject}
          className="group inline-flex shrink-0 items-center justify-center gap-2 rounded-full px-5 py-2.5 text-[16px] font-semibold text-white transition-all duration-300 hover:-translate-y-0.5"
          style={{ background: C.success }}
        >
          Retour à mon monument
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
  subscription: BillingSubscription | null;
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
            className="inline-flex items-center gap-2 text-[15px] font-medium"
            style={{ color: C.grayFg }}
          >
            <IconSucces className="h-3.5 w-3.5 shrink-0" style={{ color: C.success }} />
            {item}
          </span>
        ))}
      </div>

      {(subscription || onOpenPortal) && (
        <p className="text-center text-[15px]" style={{ color: C.grayMuted }}>
          {subscription?.cancelAtPeriodEnd && periodEnd
            ? `Votre abonnement prend fin le ${periodEnd}. Votre offre reste active jusque-là.`
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
