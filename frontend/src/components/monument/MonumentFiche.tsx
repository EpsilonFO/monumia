import type { ComponentType, ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import {
  IconMonument, IconProtection, IconDiagnostic, IconChantier, IconLocalisation,
  IconCalendrier, IconParchemin, IconRegle, IconCle, IconCompte, IconPublic,
  IconListe, IconMaison, IconLivre, IconImage, IconModifier, IconSupprimer,
  IconSucces,
} from '@/components/icons';
import { Clover, AllClear } from '@/components/illustrations';
import { C, SERIF } from '@/lib/brand';
import { formatDate } from '@/lib/date-utils';
import {
  PROTECTION_LABELS, isEnPeril, perilLabel, OWNERSHIP_TYPES,
  WORK_TYPES, MATERIAUX, TYPES_COUVERTURE, URGENCE_TRAVAUX,
} from '@/constants/monument-options';
import type { Monument } from '@/types';

type IconType = ComponentType<{ className?: string; strokeWidth?: number; style?: React.CSSProperties }>;

/* ------------------------------------------------------------------ */
/* Tonalités par valeur métier                                         */
/* ------------------------------------------------------------------ */

// Chaque niveau de protection a sa couleur et une phrase qui explique, en
// langage courant, ce que ce statut change concrètement pour le propriétaire.
const PROTECTION_TONE: Record<string, { bg: string; fg: string; sub: string }> = {
  classe: {
    bg: 'var(--secondary)', fg: 'var(--primary)',
    sub: "Le plus haut niveau de protection au titre des Monuments Historiques : les aides de l'État vous sont largement ouvertes.",
  },
  inscrit: {
    bg: 'var(--info-muted)', fg: 'var(--info)',
    sub: 'Une protection officielle qui ouvre droit à de nombreuses aides publiques.',
  },
  abords: {
    bg: 'var(--cat-3-soft)', fg: 'var(--cat-3)',
    sub: "Votre bien se trouve dans le périmètre protégé d'un monument historique.",
  },
  spr: {
    bg: 'var(--cat-4-soft)', fg: 'var(--cat-4)',
    sub: 'Un site reconnu pour la valeur de son patrimoine architectural et paysager.',
  },
  non_protege: {
    bg: 'var(--muted)', fg: 'var(--gray-fg)',
    sub: 'Pas encore de protection officielle — certaines aides restent néanmoins accessibles.',
  },
};

// Pastille de couleur associée au signal péril (simple repère visuel).
const PERIL_DOT = { oui: 'var(--destructive)', non: 'var(--success)' };

const URGENCE_TONE: Record<string, { fg: string; bg: string }> = {
  faible:   { fg: 'var(--info)',        bg: 'var(--info-muted)' },
  moyenne:  { fg: 'var(--warning)',     bg: 'var(--warning-muted)' },
  haute:    { fg: 'var(--destructive)', bg: 'var(--destructive-muted)' },
  critique: { fg: '#fff',               bg: 'var(--destructive)' },
};

const PHOTO_TYPE_LABELS: Record<string, string> = {
  facade: 'Façade',
  interieur: 'Intérieur',
  detail: 'Détail',
  aerien: 'Vue aérienne',
  degradation: 'Dégradation',
};

const WORK_LABELS = Object.fromEntries(WORK_TYPES.map((w) => [w.value, w.label]));
const MATERIAU_LABELS = Object.fromEntries(MATERIAUX.map((m) => [m.value, m.label]));
const COUVERTURE_LABELS = Object.fromEntries(TYPES_COUVERTURE.map((t) => [t.value, t.label]));
const URGENCE_LABELS = Object.fromEntries(URGENCE_TRAVAUX.map((u) => [u.value, u.label]));

/* ------------------------------------------------------------------ */
/* Briques d'affichage                                                 */
/* ------------------------------------------------------------------ */

function Section({ icon: Icon, title, iconBg = 'var(--secondary)', iconFg = 'var(--primary)', accent, children }: {
  icon: IconType;
  title: ReactNode;
  iconBg?: string;
  iconFg?: string;
  /** Filet coloré sur la tranche gauche (même signature que les encadrés du blog). */
  accent?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={`relative flex flex-col overflow-hidden rounded-2xl border p-5 sm:p-6 ${accent ? 'pl-6 sm:pl-7' : ''}`}
      style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
    >
      {accent && <span aria-hidden className="absolute inset-y-0 left-0 w-1.5" style={{ background: accent }} />}
      <h3 className="mb-4 flex items-center gap-2.5 text-[17px]" style={{ fontFamily: SERIF, color: C.ink }}>
        <span
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
          style={{ background: iconBg, color: iconFg }}
        >
          <Icon className="h-[16px] w-[16px]" strokeWidth={2} />
        </span>
        {title}
      </h3>
      {children}
    </section>
  );
}

function Field({ icon: Icon, label, value, dot }: { icon: IconType; label: string; value: string; dot?: string }) {
  return (
    <div className="flex items-start gap-3">
      <span
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border"
        style={{ background: '#fff', borderColor: C.border, color: C.blue }}
      >
        <Icon className="h-[17px] w-[17px]" strokeWidth={1.8} />
      </span>
      <div className="min-w-0">
        <p className="text-[12px] font-semibold uppercase leading-none tracking-[0.08em]" style={{ color: C.grayMuted }}>{label}</p>
        <p className="mt-1.5 flex items-center gap-2 text-[15px] font-medium leading-snug" style={{ color: C.ink }}>
          {dot && <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: dot }} aria-hidden />}
          {value}
        </p>
      </div>
    </div>
  );
}

/** Description : la première phrase en serif donne le ton, la suite en corps courant.
 *  Pas de mise en avant si la « phrase » est douteuse (parenthèse ouverte, abréviation
 *  type « cad. » fréquente dans les notices Mérimée). */
function Description({ text }: { text: string }) {
  const cut = text.indexOf('. ');
  const head = cut > 0 && cut < 220 ? text.slice(0, cut + 1) : '';
  const balanced = (head.match(/\(/g)?.length ?? 0) === (head.match(/\)/g)?.length ?? 0);
  const abbrev = /\b(cad|art|av|ex|réf|vol|chap|n[o°]|[a-z])\.$/i.test(head.trim());
  const lead = head && balanced && !abbrev ? head : '';
  const body = lead ? text.slice(cut + 1).trim() : text;
  return (
    <div className="space-y-2.5">
      {lead && <p className="text-[18px] leading-snug" style={{ fontFamily: SERIF, color: C.ink }}>{lead}</p>}
      {body && (
        <p className="whitespace-pre-line text-[14.5px] leading-relaxed" style={{ color: C.grayFg }}>{body}</p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Fiche complète                                                      */
/* ------------------------------------------------------------------ */

interface MonumentFicheProps {
  monument: Monument;
  canDelete: boolean;
  deleting: boolean;
  onDelete: () => void;
}

export function MonumentFiche({ monument, canDelete, deleting, onDelete }: MonumentFicheProps) {
  const protection = PROTECTION_TONE[monument.protection] ?? PROTECTION_TONE.non_protege;
  const urgence = monument.urgenceTravaux ? URGENCE_TONE[monument.urgenceTravaux] : null;
  const travaux = monument.travauxEnvisages ?? [];
  const enPeril = isEnPeril(monument.etatConservation);

  // Fiche info : seuls les champs renseignés apparaissent.
  const fields = [
    monument.referenceMerimee && { icon: IconParchemin, label: 'Réf. Mérimée', value: monument.referenceMerimee },
    monument.commune && { icon: IconLocalisation, label: 'Commune', value: monument.commune },
    monument.departement && { icon: IconPublic, label: 'Département', value: monument.departement },
    monument.siecleConstruction && {
      icon: IconCalendrier, label: 'Siècle de construction',
      // Les données Mérimée arrivent parfois sous la forme « 12e s.;13e s. ».
      value: monument.siecleConstruction.split(';').map((s) => s.trim()).filter(Boolean).join(' · '),
    },
    monument.periodeConstruction?.length && { icon: IconCalendrier, label: 'Période', value: monument.periodeConstruction.join(' · ') },
    monument.proprietaire && {
      icon: IconCle, label: 'Propriétaire',
      value: OWNERSHIP_TYPES.find((o) => o.value === monument.proprietaire)?.label ?? monument.proprietaire,
    },
    monument.affectataire && { icon: IconCompte, label: 'Affectation', value: monument.affectataire },
    monument.superficie && { icon: IconRegle, label: 'Superficie', value: `${monument.superficie.toLocaleString('fr-FR')} m²` },
    monument.nombreNiveaux && { icon: IconListe, label: 'Niveaux', value: `${monument.nombreNiveaux} ${monument.nombreNiveaux > 1 ? 'niveaux' : 'niveau'}` },
    monument.typeCouverture && { icon: IconMaison, label: 'Couverture', value: COUVERTURE_LABELS[monument.typeCouverture] ?? monument.typeCouverture },
    monument.materiaux?.length && { icon: IconChantier, label: 'Matériaux', value: monument.materiaux.map((m) => MATERIAU_LABELS[m] ?? m).join(', ') },
    // Tant que la question péril n'a pas été posée (fiche créée avant l'étape
    // « Votre projet »), la ligne n'apparaît pas plutôt que d'afficher un vide.
    enPeril !== null && {
      icon: IconDiagnostic, label: 'État du monument',
      value: perilLabel(monument.etatConservation) ?? '',
      dot: enPeril ? PERIL_DOT.oui : PERIL_DOT.non,
    },
  ].filter((f): f is { icon: IconType; label: string; value: string; dot?: string } => Boolean(f));

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Fiche info — la pièce maîtresse : fond légèrement teinté + quadrilobe fantôme. */}
      <section
        className="relative overflow-hidden rounded-2xl border p-5 sm:p-6"
        style={{
          background: 'linear-gradient(135deg, var(--secondary) 0%, var(--card) 48%)',
          borderColor: C.border,
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <Clover
          size={140}
          className="pointer-events-none absolute -right-6 -top-7"
          style={{ color: C.blue, opacity: 0.06 }}
        />
        <h3 className="mb-4 flex items-center gap-2.5 text-[17px]" style={{ fontFamily: SERIF, color: C.ink }}>
          <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg" style={{ background: C.blue, color: '#fff' }}>
            <IconMonument className="h-[16px] w-[16px]" strokeWidth={2} />
          </span>
          Fiche info
        </h3>
        {fields.length > 0 ? (
          <div className="relative grid grid-cols-1 gap-x-6 gap-y-5 sm:grid-cols-2 lg:grid-cols-3">
            {fields.map((f) => <Field key={f.label} icon={f.icon} label={f.label} value={f.value} dot={f.dot} />)}
          </div>
        ) : (
          <p className="text-[14px]" style={{ color: C.grayMuted }}>
            Les informations du monument apparaîtront ici une fois la fiche renseignée.
          </p>
        )}
      </section>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Section icon={IconProtection} title="Protection" iconBg={protection.bg} iconFg={protection.fg} accent={protection.fg}>
          <div className="space-y-3">
            <div className="rounded-xl p-4" style={{ background: protection.bg }}>
              <p className="text-[16px] font-bold leading-snug" style={{ color: protection.fg }}>
                {PROTECTION_LABELS[monument.protection] ?? monument.protection}
              </p>
              <p className="mt-1.5 text-[13.5px] leading-relaxed" style={{ color: C.grayFg }}>{protection.sub}</p>
            </div>
            {/* Un bien non protégé peut garder d'anciennes dates en base : on ne les montre pas. */}
            {monument.protection !== 'non_protege' && monument.dateProtection && (
              <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px] font-medium" style={{ background: C.cream, color: C.grayFg }}>
                <IconCalendrier className="h-3.5 w-3.5" />
                Protégé depuis le {formatDate(monument.dateProtection)}
              </span>
            )}
          </div>
        </Section>

        <Section icon={IconChantier} title="Travaux envisagés" iconBg={C.paleOrange} iconFg={C.orange} accent={C.orange}>
          {travaux.length === 0 && !urgence && !monument.descriptionEtat && !monument.derniersTravaux && !monument.diagnosticRealise ? (
            /* Rien à afficher du tout : état vide centré dans la carte. */
            <div className="flex flex-1 flex-col items-center justify-center gap-3 py-2 text-center">
              <AllClear />
              <p className="text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
                Aucun travail prévu pour le moment.
              </p>
            </div>
          ) : (
          <div className="space-y-3.5">
            {travaux.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {travaux.map((t) => (
                  <span key={t} className="inline-flex items-center rounded-full px-3 py-1.5 text-[13px] font-semibold" style={{ background: C.paleOrange, color: C.orange }}>
                    {WORK_LABELS[t] ?? t}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-[14px]" style={{ color: C.grayMuted }}>Aucun travail prévu pour le moment.</p>
            )}
            {urgence && monument.urgenceTravaux && (
              <div className="flex items-center gap-2 text-[13.5px]" style={{ color: C.grayFg }}>
                <span>Urgence :</span>
                <span className="inline-flex items-center rounded-full px-3 py-1 text-[12.5px] font-semibold" style={{ background: urgence.bg, color: urgence.fg }}>
                  {URGENCE_LABELS[monument.urgenceTravaux] ?? monument.urgenceTravaux}
                </span>
              </div>
            )}
            {monument.descriptionEtat && (
              <p className="text-[13.5px] leading-relaxed" style={{ color: C.grayFg }}>
                <span className="font-semibold" style={{ color: C.ink }}>État constaté : </span>
                {monument.descriptionEtat}
              </p>
            )}
            {monument.derniersTravaux && (
              <p className="text-[13.5px] leading-relaxed" style={{ color: C.grayFg }}>
                <span className="font-semibold" style={{ color: C.ink }}>Derniers travaux : </span>
                {monument.derniersTravaux}
              </p>
            )}
            {monument.diagnosticRealise && (
              <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px] font-semibold" style={{ background: C.successMuted, color: C.success }}>
                <IconSucces className="h-3.5 w-3.5" />
                Diagnostic déjà réalisé
              </span>
            )}
          </div>
          )}
        </Section>
      </div>

      {monument.descriptionGenerale && (
        <Section icon={IconLivre} title="Description du monument" accent={C.blue}>
          <Description text={monument.descriptionGenerale} />
        </Section>
      )}

      {monument.photos && monument.photos.length > 0 && (
        <Section icon={IconImage} title="Photos" iconBg={C.paleBlue} iconFg={C.blue} accent={C.blueLight}>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {monument.photos.map((p) => (
              <figure key={p.url} className="group min-w-0">
                <div className="aspect-[4/3] overflow-hidden rounded-xl border" style={{ borderColor: C.border }}>
                  <img
                    src={p.url}
                    alt={p.legende || monument.nom}
                    loading="lazy"
                    className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
                  />
                </div>
                {(p.legende || PHOTO_TYPE_LABELS[p.type]) && (
                  <figcaption className="mt-1.5 flex items-center gap-2 text-[12.5px]" style={{ color: C.grayMuted }}>
                    {PHOTO_TYPE_LABELS[p.type] && (
                      <span className="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ background: C.paleBlue, color: C.blue }}>
                        {PHOTO_TYPE_LABELS[p.type]}
                      </span>
                    )}
                    {p.legende && <span className="truncate">{p.legende}</span>}
                  </figcaption>
                )}
              </figure>
            ))}
          </div>
        </Section>
      )}

      <div className="flex flex-col gap-3 pt-1 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px]" style={{ color: C.grayMuted }}>
          <span className="flex items-center gap-1.5">
            <IconCalendrier className="h-3.5 w-3.5" />
            Créé le {formatDate(monument.createdAt)}
          </span>
          <span className="flex items-center gap-1.5">
            <IconModifier className="h-3.5 w-3.5" />
            Modifié le {formatDate(monument.updatedAt)}
          </span>
        </div>
        {canDelete && (
          <button
            onClick={onDelete}
            disabled={deleting}
            className="inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[13px] font-semibold transition-colors hover:bg-destructive-muted disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            style={{ borderColor: C.border, color: C.danger }}
          >
            {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <IconSupprimer className="h-4 w-4" strokeWidth={1.8} />}
            Supprimer le projet
          </button>
        )}
      </div>
    </div>
  );
}
