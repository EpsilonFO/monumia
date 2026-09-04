import { useNavigate } from 'react-router';
import { ChevronRight, ArrowRight } from 'lucide-react';
import {
  IconSucces,
  IconErreur,
  IconHelp,
  IconCle,
  IconLienExterne,
  IconTemps,
  IconEcheance,
  IconCalendrier,
  IconSubvention,
  IconTendance,
  IconInstitution,
  IconPublic,
  IconDevis,
  IconAide,
} from '@/components/icons';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AIDE_CATEGORIES } from '@/constants/aide-categories';
import { ROUTES } from '@/constants/routes';
import { formatCurrency, formatPercentage } from '@/lib/format-utils';
import { daysUntil, formatDateShort } from '@/lib/date-utils';
import { C, SERIF } from '@/lib/brand';
import {
  DISPONIBILITE_BIENTOT_PILL,
  getDisponibilite,
  getEligibilityStatus,
  STATUS_BADGE,
  STATUS_PILL_LABEL,
  STATUS_TONE,
} from './eligibility-status';
import type { AideMatchResult } from '@/types';

interface AideCardProps {
  match: AideMatchResult;
  showEligibility?: boolean;
  /**
   * Le bandeau pâle « Montant max / des travaux / Échéance ». Retiré en offre
   * gratuite : ces chiffres restent lisibles sur la fiche de l'aide, mais mis
   * en tête de chaque carte ils promettent un plan de financement que l'offre
   * ne suit pas encore.
   */
  showChiffres?: boolean;
  /** Le PROJET dans lequel l'aide est vue : c'est lui qui clé la fiche d'aide. */
  projetId?: string;
  /**
   * `tile` = vignette compacte (non éligibles) · `grid` = carte « opportunité »
   * verticale (≥ 2 aides) · `hero` = grande carte pleine largeur (1 seule aide).
   */
  layout?: 'tile' | 'grid' | 'hero';
}

type Urgency = 'urgent' | 'warning' | 'normal' | 'past';

// Seuils adaptés au patrimoine (instruction des dossiers longue) :
// dépassée / < 30 j → rouge · 30–100 j → orange · > 100 j → bleu.
function deadlineInfo(date: string): { urgency: Urgency; text: string } {
  const days = daysUntil(date);
  if (days < 0) return { urgency: 'past', text: 'Échéance dépassée' };
  if (days === 0) return { urgency: 'urgent', text: "Dernier jour" };
  if (days === 1) return { urgency: 'urgent', text: 'Demain' };
  if (days < 30) return { urgency: 'urgent', text: `Dans ${days} jours` };
  if (days <= 100) return { urgency: 'warning', text: `Avant le ${formatDateShort(date)}` };
  return { urgency: 'normal', text: `Avant le ${formatDateShort(date)}` };
}

// Pastille : l'intensité visuelle suit l'urgence.
// Rouge proche/dépassé → pleine + halo (attire l'œil) ; orange → légère ; bleu lointain → calme.
const DEADLINE_PILL: Record<Urgency, string> = {
  urgent: 'px-3 py-1.5 rounded-lg text-sm font-bold bg-destructive text-destructive-foreground shadow-md shadow-destructive/40',
  past: 'px-3 py-1.5 rounded-lg text-sm font-bold bg-destructive text-destructive-foreground shadow-md shadow-destructive/40 line-through',
  warning: 'px-2.5 py-1 rounded-lg border text-xs font-semibold bg-warning-muted text-warning border-warning',
  normal: 'px-2.5 py-1 rounded-lg border text-xs font-semibold bg-info-muted text-info border-info',
};

// Barre d'accent latérale : repère dans la grille pour les échéances proches.
// Rien pour le lointain (bleu) afin de ne pas surcharger.
const DEADLINE_STRIPE: Record<Urgency, string> = {
  urgent: 'bg-destructive',
  past: 'bg-destructive',
  warning: 'bg-warning',
  normal: 'bg-info',
};

// Pastille ronde par catégorie d'aide — petite touche d'identité reprise de la
// landing (icône dans un cercle teinté).
const CATEGORY_ICON: Record<string, typeof IconInstitution> = {
  etat_drac: IconInstitution,
  region: IconInstitution,
  departement: IconInstitution,
  fondation: IconInstitution,
  europe: IconPublic,
  mecenat: IconSubvention,
  fiscalite: IconDevis,
  autre: IconAide,
};

export function AideCard({
  match,
  showEligibility = true,
  showChiffres = true,
  projetId,
  layout = 'tile',
}: AideCardProps) {
  const { aide, criteresRemplis, criteresNonRemplis } = match;
  const navigate = useNavigate();
  const categoryConfig = AIDE_CATEGORIES.find((c) => c.value === aide.categorie);
  const status = getEligibilityStatus(match);
  const deadline = !aide.permanent && aide.dateLimite ? deadlineInfo(aide.dateLimite) : null;
  // Fenêtre fermée : la date limite affichée est celle de la session écoulée,
  // pas une échéance manquée. Toute la signalétique rouge est neutralisée — le
  // message est « revenez à la prochaine session », pas « c'est raté ».
  const bientot = getDisponibilite(match) === 'bientot';
  const redAlert = !bientot && (deadline?.urgency === 'urgent' || deadline?.urgency === 'past');
  const DeadlineIcon = redAlert ? IconTemps : IconEcheance;
  const CategoryIcon = CATEGORY_ICON[aide.categorie] ?? IconAide;
  const statusTone = STATUS_TONE[status];
  const statusBadge = STATUS_BADGE[status];
  const StatusIcon = statusBadge.icon;
  const aideDetailUrl = projetId
    ? ROUTES.PROJET_AIDE(projetId, aide.id)
    : ROUTES.MONUMENTS;

  const hoverClass =
    status === 'eligible'
      ? 'hover:border-success'
      : status === 'atteignable'
        ? 'hover:border-info'
        : status === 'potential'
          ? 'hover:border-warning'
          : 'hover:border-border';

  // Le paywall des aides à venir vit au niveau de la SECTION, qui les floute et
  // les rend inertes : plus rien à intercepter ici.
  const handleCardClick = () => navigate(aideDetailUrl);

  // Animation volontairement minimale : une simple ombre au survol, rien de plus.
  const cardBase = `group relative overflow-hidden cursor-pointer transition duration-200 hover:shadow-md ${hoverClass} ${redAlert ? 'ring-2 ring-destructive/70' : ''}`;

  // Pièces partagées entre la vignette (`tile`) et la ligne (`row`) — même contenu,
  // agencement différent.
  const stripe = deadline && DEADLINE_STRIPE[deadline.urgency] ? (
    <div
      className={`absolute inset-y-0 left-0 ${redAlert ? 'w-1.5' : 'w-1'} ${bientot ? DEADLINE_STRIPE.normal : DEADLINE_STRIPE[deadline.urgency]}`}
      aria-hidden
    />
  ) : null;

  // Pastille « Ouvre bientôt » : le pendant calendaire du statut, affichée à
  // côté de lui (hero, grid) ou dans la rangée de badges (tile).
  const BientotIcon = DISPONIBILITE_BIENTOT_PILL.icon;
  const bientotPill = bientot ? (
    <span
      className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold"
      style={{ background: DISPONIBILITE_BIENTOT_PILL.tint, color: DISPONIBILITE_BIENTOT_PILL.accent }}
    >
      <BientotIcon className="h-3 w-3" />
      {DISPONIBILITE_BIENTOT_PILL.label}
    </span>
  ) : null;

  const badges = (
    <div className="flex items-center gap-2 flex-wrap">
      <Badge className={categoryConfig?.color ?? 'bg-muted text-muted-foreground'}>
        {categoryConfig?.label ?? aide.categorie}
      </Badge>
      {showEligibility && (
        <Badge variant="outline" className={statusBadge.className}>
          <StatusIcon className="h-3 w-3 mr-1" />
          {statusBadge.label}
        </Badge>
      )}
      {bientot && (
        <Badge variant="outline" className={`${DISPONIBILITE_BIENTOT_PILL.className} gap-1`}>
          <BientotIcon className="h-2.5 w-2.5" />
          {DISPONIBILITE_BIENTOT_PILL.label}
        </Badge>
      )}
    </div>
  );

  const title = <CardTitle className="text-base leading-tight">{aide.nomCourt}</CardTitle>;

  const description = (className = '') => (
    <p className={`text-sm text-muted-foreground line-clamp-2 ${className}`}>{aide.description}</p>
  );

  // Fenêtre fermée : le badge « Ouvre bientôt » de la rangée du haut porte déjà
  // l'information calendaire — inutile de doubler avec une date de session close.
  const deadlinePill = deadline && !bientot ? (
    <span className={`inline-flex items-center gap-1.5 ${DEADLINE_PILL[deadline.urgency]}`}>
      <DeadlineIcon className={redAlert ? 'h-4 w-4' : 'h-3.5 w-3.5'} />
      {deadline.text}
    </span>
  ) : null;

  const criteria = showEligibility ? (
    <div className="space-y-1">
      {criteresRemplis.slice(0, 3).map((c, i) => (
        <div key={i} className="flex items-center gap-1.5 text-xs text-success">
          <IconSucces className="h-3 w-3 shrink-0" />
          <span>{c}</span>
        </div>
      ))}
      {criteresNonRemplis.slice(0, 2).map((c, i) => (
        <div key={i} className="flex items-center gap-1.5 text-xs text-destructive">
          <IconErreur className="h-3 w-3 shrink-0" />
          <span>{c}</span>
        </div>
      ))}
      {status === 'atteignable' && (match.leviers ?? []).slice(0, 2).map((levier, i) => (
        <div key={`lev-${i}`} className="flex items-start gap-1.5 text-xs text-info">
          <IconCle className="mt-0.5 h-3 w-3 shrink-0" />
          <span>{levier.resume}</span>
        </div>
      ))}
      {status === 'potential' && match.llmEvaluation?.incertitudes.slice(0, 2).map((c, i) => {
        const isClarified = typeof c !== 'string' && c.clarified;
        return (
          <div key={i} className={`flex items-center gap-1.5 text-xs ${isClarified ? 'text-success' : 'text-warning'}`}>
            {isClarified ? <IconSucces className="h-3 w-3 shrink-0" /> : <IconHelp className="h-3 w-3 shrink-0" />}
            <span>{typeof c === 'string' ? c : c.detail}</span>
          </div>
        );
      })}
    </div>
  ) : null;

  const officialLink = aide.urlOfficielle ? (
    <Button asChild size="sm" variant="ghost" onClick={(e) => e.stopPropagation()}>
      <a href={aide.urlOfficielle} target="_blank" rel="noopener noreferrer">
        <IconLienExterne className="h-3 w-3 mr-1" />
        Site officiel
      </a>
    </Button>
  ) : null;

  // Statut clair façon SaaS grand public : pastille à pré-point coloré.
  // « À confirmer » plutôt que « Potentiellement éligible » — plus simple à lire.
  const statusPill = showEligibility ? (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold" style={{ background: statusTone.tint, color: statusTone.accent }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: statusTone.accent }} />
      {STATUS_PILL_LABEL[status]}
    </span>
  ) : null;

  // Récap rassurant en une ligne — le détail complet est sur la fiche de l'aide.
  const criteriaSummary = criteresRemplis.length > 0 ? (
    <span className="inline-flex items-center gap-1.5 text-[12.5px] font-medium" style={{ color: 'var(--success)' }}>
      <IconSucces className="h-3.5 w-3.5 shrink-0" />
      {criteresRemplis.length} critère{criteresRemplis.length > 1 ? 's' : ''} rempli{criteresRemplis.length > 1 ? 's' : ''}
    </span>
  ) : null;

  // Informations clés en lignes « icône + libellé + valeur » — lisibles d'un
  // coup d'œil, sans capsules ni traits de séparation.
  const dRed = redAlert;
  const dTone = !deadline
    ? { bg: C.paleBlue, fg: C.blue }
    : dRed
      ? { bg: C.paleDanger, fg: C.danger }
      : deadline.urgency === 'warning'
        ? { bg: C.paleOrange, fg: C.orange }
        : { bg: C.paleBlue, fg: C.blue };
  // Valeur courte pour l'encadré : le libellé « Échéance » porte déjà le sens,
  // la date seule suffit (« Avant le … » ferait passer la valeur sur 2 lignes).
  const deadlineFactValue = bientot
    ? 'Prochaine session'
    : !deadline
      ? aide.permanent
        ? "Toute l'année"
        : 'Sur demande'
      : deadline.urgency === 'past'
        ? 'Dépassée'
        : deadline.urgency === 'urgent'
          ? deadline.text
          : formatDateShort(aide.dateLimite ?? '');
  const facts: { icon: typeof IconSubvention; accent: string; label: string; value: string; valueColor?: string }[] = [];
  if (aide.montantMax != null) facts.push({ icon: IconSubvention, accent: C.orange, label: 'Montant max', value: formatCurrency(aide.montantMax) });
  if (aide.tauxMax != null) facts.push({ icon: IconTendance, accent: C.blue, label: 'des travaux', value: `${aide.tauxMax} %` });
  facts.push({
    icon: deadline && !bientot ? DeadlineIcon : IconCalendrier,
    accent: dTone.fg,
    label: 'Échéance',
    value: deadlineFactValue,
    valueColor: deadline ? dTone.fg : undefined,
  });

  // Bouton principal clair — signal d'action fort, en bleu charte.
  const detailButton = (fullWidth: boolean) => (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); handleCardClick(); }}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-[13.5px] font-semibold text-white transition-shadow duration-200 hover:shadow-md ${fullWidth ? 'w-full' : ''}`}
      style={{ background: C.blue }}
    >
      Voir l'aide
      <ArrowRight className="h-4 w-4" />
    </button>
  );

  // Montants en ligne — vignette uniquement (la ligne `row` utilise le panneau « gain »).
  const amountsInline = (
    <div className="flex items-center gap-3 flex-wrap text-sm">
      {aide.tauxMax && (
        <span className="font-medium text-primary">Jusqu'à {formatPercentage(aide.tauxMax)}</span>
      )}
      {aide.montantMax && (
        <span className="font-medium text-primary">Max {formatCurrency(aide.montantMax)}</span>
      )}
      {aide.permanent && (
        <span className="text-muted-foreground flex items-center gap-1">
          <IconTemps className="h-3 w-3" />
          Permanent
        </span>
      )}
    </div>
  );

  // HERO — une seule aide : bandeau pleine largeur qui occupe l'espace. Identité +
  // description à gauche, panneau d'infos bleu pâle + bouton à droite. Bleu en
  // accents, sans gros bloc ni trait de séparation.
  if (layout === 'hero') {
    return (
      <Card className={`${cardBase} gap-0 py-0`} onClick={handleCardClick}>
        <div className="flex flex-col gap-6 p-6 sm:p-7 lg:flex-row lg:gap-8">
          <div className="min-w-0 flex-1 space-y-3">
            <div className="flex items-start gap-3">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl" style={{ background: C.paleBlue }}>
                <CategoryIcon className="h-6 w-6" style={{ color: C.blue }} strokeWidth={1.7} />
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-[20px] leading-snug" style={{ fontFamily: SERIF, color: C.blue }}>
                    {aide.nomCourt}
                  </h3>
                  {statusPill}
                  {bientotPill}
                </div>
                <p className="mt-1 text-[11px] font-bold uppercase tracking-wider" style={{ color: C.blue }}>{categoryConfig?.label ?? aide.categorie}</p>
              </div>
            </div>
            {description()}
            {criteriaSummary}
          </div>
          <div className="flex shrink-0 flex-col gap-4 lg:w-72">
            {showChiffres && (
            <div className="space-y-3 rounded-xl p-4" style={{ background: C.paleBlue }}>
              {facts.map((f, i) => {
                const Icon = f.icon;
                return (
                  <div key={i} className="flex items-center gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white">
                      <Icon className="h-[18px] w-[18px]" style={{ color: f.accent }} strokeWidth={1.8} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-[15px] font-bold leading-tight" style={{ color: f.valueColor ?? C.ink }}>{f.value}</p>
                      <p className="text-[11px] text-muted-foreground">{f.label}</p>
                    </div>
                  </div>
                );
              })}
            </div>
            )}
            {detailButton(true)}
          </div>
        </div>
      </Card>
    );
  }

  // GRID — deux aides ou plus : carte compacte verticale, le bandeau d'infos pâle
  // remplit le bas. Colonnes du bandeau ajustées au nombre d'infos (jamais de vide).
  if (layout === 'grid') {
    return (
      <Card className={`${cardBase} h-full gap-0 py-0`} onClick={handleCardClick}>
        <div className="flex h-full flex-col gap-3 p-5">
          {/* Rang d'identité à hauteur fixe : icône + catégorie mise en avant,
              statut à droite — le titre passe en dessous, en pleine largeur. */}
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" style={{ background: C.paleBlue }}>
              <CategoryIcon className="h-[18px] w-[18px]" style={{ color: C.blue }} strokeWidth={1.7} />
            </div>
            <span className="min-w-0 truncate text-[11px] font-bold uppercase tracking-wider" style={{ color: C.blue }}>
              {categoryConfig?.label ?? aide.categorie}
            </span>
            {/* Les pastilles ne se compriment pas : c'est la catégorie qui
                s'élide quand la carte est étroite. */}
            <span className="ml-auto flex shrink-0 items-center gap-1.5">{statusPill}{bientotPill}</span>
          </div>

          {/* Hauteur réservée sur 2 lignes pour que les cartes d'une même
              rangée gardent leurs sections alignées quel que soit le nom. */}
          <h3 className="line-clamp-2 min-h-[2lh] text-[17px] leading-snug" style={{ fontFamily: SERIF, color: C.blue }}>
            {aide.nomCourt}
          </h3>

          {description('min-h-[2lh]')}

          {showChiffres && (
          <div
            className="grid gap-3 rounded-xl px-3 py-3"
            style={{ background: C.paleBlue, gridTemplateColumns: `repeat(${facts.length}, minmax(0, 1fr))` }}
          >
            {facts.map((f, i) => {
              const Icon = f.icon;
              return (
                <div key={i} className="flex min-w-0 flex-col items-center gap-1 text-center">
                  <Icon className="h-5 w-5 shrink-0" style={{ color: f.accent }} strokeWidth={1.8} />
                  {/* Zone de valeur à hauteur fixe (2 lignes) : un encadré dont une
                      valeur se replie ne grandit plus par rapport à ses voisins. */}
                  <span className="flex min-h-[2lh] items-center text-[14px] font-bold leading-tight" style={{ color: f.valueColor ?? C.ink }}>{f.value}</span>
                  <span className="text-[10.5px] leading-tight text-muted-foreground">{f.label}</span>
                </div>
              );
            })}
          </div>
          )}

          <div className="mt-auto flex items-center justify-between gap-3 pt-1">
            <div>{criteriaSummary}</div>
            {detailButton(false)}
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className={cardBase} onClick={handleCardClick}>
      {stripe}
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1.5 flex-1 min-w-0">
            {badges}
            {title}
          </div>
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {description()}
        {deadlinePill}
        {amountsInline}
        {criteria}
        {officialLink && <div className="pt-1">{officialLink}</div>}
      </CardContent>
    </Card>
  );
}
