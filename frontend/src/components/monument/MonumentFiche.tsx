import type { ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import { IconModifier, IconSupprimer } from '@/components/icons';
import { C, SERIF } from '@/lib/brand';
import { formatDate } from '@/lib/date-utils';
import {
  PROTECTION_LABELS, isEnPeril, perilLabel, OWNERSHIP_TYPES,
} from '@/constants/monument-options';
import type { Monument } from '@/types';

/* ------------------------------------------------------------------ */
/* Ce que disent les statuts                                           */
/* ------------------------------------------------------------------ */

// L'en-tête de la fiche énonce le statut comme le fait l'arrêté — « Classé au
// titre des monuments historiques », et non le libellé court des badges. C'est
// la seule page où il se lit en entier ; ailleurs la place manque.
const PROTECTION_ENONCE: Record<string, string> = {
  classe: 'Classé au titre des monuments historiques',
  inscrit: 'Inscrit au titre des monuments historiques',
  abords: "Situé aux abords d'un monument historique",
  spr: 'En site patrimonial remarquable',
  non_protege: 'Non protégé',
};

// Ce que ce statut change concrètement pour le propriétaire, en une phrase.
const PROTECTION_PHRASE: Record<string, string> = {
  classe: "Le plus haut niveau de protection au titre des monuments historiques : les aides de l'État vous sont largement ouvertes.",
  inscrit: 'Une protection officielle qui ouvre droit à de nombreuses aides publiques.',
  abords: "Le bien se trouve dans le périmètre protégé d'un monument historique.",
  spr: 'Un site reconnu pour la valeur de son patrimoine architectural et paysager.',
  non_protege: 'Pas encore de protection officielle. Certaines aides restent néanmoins accessibles.',
};

const PERIL_PHRASE = {
  oui: "Les dispositifs d'urgence, loto du patrimoine et fonds régionaux de sauvegarde, ne s'adressent qu'aux monuments dans cette situation.",
  non: "Le monument est globalement sain. Les aides d'urgence ne vous concernent pas, les dispositifs de restauration courante restent ouverts.",
  inconnu: "La question n'a pas encore été posée. Y répondre ouvre ou écarte les dispositifs d'urgence.",
};

const PHOTO_TYPE_LABELS: Record<string, string> = {
  facade: 'Façade',
  interieur: 'Intérieur',
  detail: 'Détail',
  aerien: 'Vue aérienne',
  degradation: 'Dégradation',
};

/* ------------------------------------------------------------------ */
/* Briques                                                             */
/* ------------------------------------------------------------------ */

/** Un fait d'identification : l'étiquette au-dessus, la valeur en serif juste
 *  en dessous. Les deux se touchent — une étiquette à gauche et sa valeur au
 *  bout d'une ligne de 500 px obligent l'œil à faire l'aller-retour. */
function Fait({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[13px] leading-snug" style={{ color: C.grayMuted }}>{label}</dt>
      <dd className="mt-1 text-[17px] leading-snug" style={{ fontFamily: SERIF, color: C.ink }}>{value}</dd>
    </div>
  );
}

/** Titre de section, dans la feuille : une étiquette discrète, pas un titre qui
 *  concurrence son propre contenu — la description s'ouvre sur du serif 21 px,
 *  un intertitre plus gros lui passerait devant. Pas de pastille d'icône non
 *  plus : le mot suffit. */
function Titre({ children }: { children: ReactNode }) {
  return (
    <h3 className="mb-3.5 text-[13.5px] font-medium leading-snug" style={{ color: C.grayMuted }}>
      {children}
    </h3>
  );
}

/** Un statut de l'en-tête : l'énoncé en grand, puis ce qu'il change. */
function Statut({ enonce, phrase, note, pastille }: {
  enonce: string;
  phrase: string;
  /** Sous l'énoncé : la date de l'arrêté, quand il y en a une. */
  note?: string;
  pastille?: string;
}) {
  return (
    <div>
      <p className="flex items-baseline gap-2.5 text-[22px] leading-[1.3]" style={{ fontFamily: SERIF, color: C.ink }}>
        {pastille && (
          <span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: pastille }} />
        )}
        {enonce}
      </p>
      {note && <p className="mt-1 text-[13.5px]" style={{ color: C.grayMuted }}>{note}</p>}
      <p className="mt-2.5 max-w-[60ch] text-[14.5px] leading-[1.65]" style={{ color: C.grayFg }}>{phrase}</p>
    </div>
  );
}

/** Description : la première phrase donne le ton en plus gros, la suite au
 *  corps courant. Pas de mise en avant si la « phrase » est douteuse (parenthèse
 *  ouverte, abréviation type « cad. » fréquente dans les notices Mérimée). */
function Description({ text }: { text: string }) {
  const cut = text.indexOf('. ');
  const head = cut > 0 && cut < 220 ? text.slice(0, cut + 1) : '';
  const balanced = (head.match(/\(/g)?.length ?? 0) === (head.match(/\)/g)?.length ?? 0);
  const abbrev = /\b(cad|art|av|ex|réf|vol|chap|n[o°]|[a-z])\.$/i.test(head.trim());
  const lead = head && balanced && !abbrev ? head : '';
  const body = lead ? text.slice(cut + 1).trim() : text;
  return (
    <div className="max-w-[74ch] space-y-4">
      {lead && (
        <p className="text-[21px] leading-[1.55]" style={{ fontFamily: SERIF, color: C.ink }}>{lead}</p>
      )}
      {body && (
        <p className="whitespace-pre-line text-[16.5px] leading-[1.8]" style={{ color: C.grayFg }}>{body}</p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Fiche complète                                                      */
/* ------------------------------------------------------------------ */

interface MonumentFicheProps {
  monument: Monument;
  canEdit: boolean;
  onEdit: () => void;
  canDelete: boolean;
  deleting: boolean;
  onDelete: () => void;
}

/**
 * Fiche sanitaire du monument : ce qui décrit le BIEN et ne bouge pas d'un
 * chantier à l'autre. Les travaux envisagés n'y figurent plus — ils cadrent un
 * projet, et vivent sur sa propre page.
 *
 * Une SEULE feuille pleine largeur, découpée par des filets, plutôt qu'une pile
 * d'encadrés de largeurs différentes : la fiche est un document, pas un
 * assemblage de vignettes. Elle s'ouvre sur les deux statuts qui gouvernent
 * l'éligibilité aux aides (protection, état sanitaire) ; viennent ensuite
 * l'identification, la description, les photos.
 */
export function MonumentFiche({
  monument, canEdit, onEdit, canDelete, deleting, onDelete,
}: MonumentFicheProps) {
  // La photo de profil illustre déjà l'en-tête : pas de doublon dans la galerie.
  // Sans lien signé, l'image serait cassée (bucket privé) — on l'écarte.
  const galerie = (monument.photos ?? []).filter((p) => p.type !== 'profil' && p.signedUrl);
  const enPeril = isEnPeril(monument.etatConservation);

  // Un bien non protégé peut garder d'anciennes dates en base : on ne les montre pas.
  const dateArrete = monument.protection !== 'non_protege' && monument.dateProtection
    ? `Arrêté du ${formatDate(monument.dateProtection)}`
    : undefined;

  // Identification : seuls les champs renseignés apparaissent.
  const faits = [
    monument.referenceMerimee && { label: 'Référence Mérimée', value: monument.referenceMerimee },
    monument.commune && { label: 'Commune', value: monument.commune },
    monument.departement && { label: 'Département', value: monument.departement },
    monument.siecleConstruction && {
      label: 'Siècle de construction',
      // Les données Mérimée arrivent parfois sous la forme « 12e s.;13e s. ».
      value: monument.siecleConstruction.split(';').map((s) => s.trim()).filter(Boolean).join(' · '),
    },
    monument.proprietaire && {
      label: 'Propriétaire',
      value: OWNERSHIP_TYPES.find((o) => o.value === monument.proprietaire)?.label ?? monument.proprietaire,
    },
  ].filter((f): f is { label: string; value: string } => Boolean(f));

  return (
    <div className="space-y-3 animate-fade-in">
      {canEdit && (
        <div className="flex justify-end">
          <button
            onClick={onEdit}
            className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-[13px] font-semibold text-white transition-all duration-200 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            style={{ background: C.blue }}
          >
            <IconModifier className="h-3.5 w-3.5" strokeWidth={2} />
            Modifier la fiche
          </button>
        </div>
      )}

      <article
        className="overflow-hidden rounded-2xl border"
        style={{ borderColor: C.border, background: C.card, boxShadow: 'var(--shadow-card)' }}
      >
        {/* En-tête de la feuille : les deux faits qui ouvrent ou ferment les
            aides. Le fond teinté les distingue du corps de la fiche sans avoir
            à les enfermer chacun dans un encadré de plus. */}
        <div
          className="grid gap-7 p-6 sm:p-8 md:grid-cols-2 md:gap-10"
          style={{ background: 'var(--secondary)' }}
        >
          <Statut
            enonce={PROTECTION_ENONCE[monument.protection]
              ?? PROTECTION_LABELS[monument.protection]
              ?? monument.protection}
            note={dateArrete}
            phrase={PROTECTION_PHRASE[monument.protection] ?? ''}
          />
          <div
            className="md:border-l md:pl-10"
            style={{ borderColor: 'color-mix(in srgb, var(--primary) 18%, transparent)' }}
          >
            <Statut
              enonce={enPeril === null ? 'État non renseigné' : (perilLabel(monument.etatConservation) ?? '')}
              phrase={enPeril === null ? PERIL_PHRASE.inconnu : enPeril ? PERIL_PHRASE.oui : PERIL_PHRASE.non}
              pastille={enPeril === null ? C.grayMuted : enPeril ? C.danger : C.success}
            />
          </div>
        </div>

        {faits.length > 0 && (
          <dl
            className="grid gap-x-10 gap-y-7 border-t p-6 sm:grid-cols-2 sm:p-8 lg:grid-cols-3"
            style={{ borderColor: C.border }}
          >
            {faits.map((f) => <Fait key={f.label} label={f.label} value={f.value} />)}
          </dl>
        )}

        {monument.descriptionGenerale && (
          <section className="border-t p-6 sm:p-8" style={{ borderColor: C.border }}>
            <Titre>Description</Titre>
            <Description text={monument.descriptionGenerale} />
          </section>
        )}

        {galerie.length > 0 && (
          <section className="border-t p-6 sm:p-8" style={{ borderColor: C.border }}>
            <Titre>Photos</Titre>
            <div className="grid grid-cols-2 gap-x-5 gap-y-6 sm:grid-cols-3 lg:grid-cols-4">
              {galerie.map((p) => (
                <figure key={p.url} className="min-w-0 space-y-2">
                  <div className="aspect-[4/3] overflow-hidden rounded-lg border" style={{ borderColor: C.border }}>
                    <img
                      src={p.signedUrl}
                      alt={p.legende || monument.nom}
                      loading="lazy"
                      className="h-full w-full object-cover"
                    />
                  </div>
                  {(p.legende || PHOTO_TYPE_LABELS[p.type]) && (
                    <figcaption className="text-[13px] leading-snug">
                      {PHOTO_TYPE_LABELS[p.type] && (
                        <span style={{ color: C.ink }}>{PHOTO_TYPE_LABELS[p.type]}</span>
                      )}
                      {p.legende && (
                        <span style={{ color: C.grayMuted }}>
                          {PHOTO_TYPE_LABELS[p.type] ? ', ' : ''}{p.legende}
                        </span>
                      )}
                    </figcaption>
                  )}
                </figure>
              ))}
            </div>
          </section>
        )}
      </article>

      <div className="flex flex-col gap-3 px-1 pt-1 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-[13px]" style={{ color: C.grayMuted }}>
          Fiche créée le {formatDate(monument.createdAt)}, modifiée le {formatDate(monument.updatedAt)}.
        </p>
        {canDelete && (
          <button
            onClick={onDelete}
            disabled={deleting}
            className="inline-flex items-center gap-2 self-start rounded-full border px-4 py-2 text-[13px] font-semibold transition-colors hover:bg-destructive-muted disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:self-auto"
            style={{ borderColor: C.border, color: C.danger }}
          >
            {deleting
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <IconSupprimer className="h-4 w-4" strokeWidth={1.8} />}
            Supprimer le monument
          </button>
        )}
      </div>
    </div>
  );
}
