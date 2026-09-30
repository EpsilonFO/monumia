import { Loader2 } from 'lucide-react';
import { IconSupprimer } from '@/components/icons';
import { Picto } from '@/components/shared/ecrans/Picto';
import { formatDate } from '@/lib/date-utils';
import {
  PROTECTION_LABELS, isEnPeril, perilLabel,
} from '@/constants/monument-options';
import {
  affectationApplicable, architectureRomaneApplicable, libellesProprietaires, libellesTypesEdifice,
} from '@/lib/fiche-monument';
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

/** Un fait d'identification : l'étiquette au-dessus, la valeur juste dessous.
 *  Une liste (types, propriétaires) se lit en pastilles, comme dans l'en-tête. */
function Fait({ label, value }: { label: string; value: string | string[] }) {
  return (
    <div className="fm-fait">
      <dt>{label}</dt>
      {Array.isArray(value) ? (
        <dd className="fm-tags">
          {value.map((v) => (
            <span key={v} className="tag">{v}</span>
          ))}
        </dd>
      ) : (
        <dd>{value}</dd>
      )}
    </div>
  );
}

/** Un statut qui ouvre ou ferme des aides : l'énoncé en serif, puis ce qu'il
 *  change. Une colonne du bloc bleu, pas une carte à part : les deux statuts se
 *  lisent ensemble, et restent alignés en haut. */
function Statut({ titre, enonce, phrase, note, ton }: {
  titre: string;
  enonce: string;
  phrase: string;
  /** Sous l'énoncé : la date de l'arrêté, quand il y en a une. */
  note?: string;
  /** Pastille de couleur devant l'énoncé (état sanitaire). */
  ton?: 'ok' | 'alerte' | 'inconnu';
}) {
  return (
    <div className="fm-statut">
      <p className="fm-lb">{titre}</p>
      <h3>
        {ton && <i aria-hidden className={`fm-pt ${ton}`} />}
        {enonce}
      </h3>
      {note && <p className="fm-note">{note}</p>}
      <p className="fm-phrase">{phrase}</p>
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
    <div className="fm-desc">
      {lead && <p className="fm-lead">{lead}</p>}
      {body && <p className="fm-corps">{body}</p>}
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
 * chantier à l'autre. Les travaux envisagés n'y figurent plus : ils cadrent un
 * projet, et vivent sur sa propre page.
 *
 * Même dessin que les autres onglets de la page (maquettes d'écran, `.ec`) :
 * un intertitre, puis des cartes au filet bleu. Elle s'ouvre sur les deux
 * statuts qui gouvernent l'éligibilité aux aides (protection, état sanitaire) ;
 * viennent ensuite l'identification, la description, les photos.
 */
export function MonumentFiche({
  monument, canEdit, onEdit, canDelete, deleting, onDelete,
}: MonumentFicheProps) {
  // La photo de profil illustre déjà l'en-tête : pas de doublon dans la galerie.
  // Sans lien signé, l'image serait cassée (bucket privé) : on l'écarte.
  const galerie = (monument.photos ?? []).filter((p) => p.type !== 'profil' && p.signedUrl);
  const enPeril = isEnPeril(monument.etatConservation);

  // Un bien non protégé peut garder d'anciennes dates en base : on ne les montre pas.
  const dateArrete = monument.protection !== 'non_protege' && monument.dateProtection
    ? `Arrêté du ${formatDate(monument.dateProtection)}`
    : undefined;

  const typesLibelles = libellesTypesEdifice(monument);
  const proprietairesLibelles = libellesProprietaires(monument);

  // Identification : seuls les champs renseignés apparaissent.
  type FaitFiche = { label: string; value: string | string[] };
  const faits = ([
    monument.referenceMerimee && { label: 'Référence Mérimée', value: monument.referenceMerimee },
    monument.commune && { label: 'Commune', value: monument.commune },
    monument.departement && { label: 'Département', value: monument.departement },
    typesLibelles.length > 0 && {
      label: typesLibelles.length > 1 ? "Types d'édifice" : "Type d'édifice",
      value: typesLibelles,
    },
    // Une précision ne s'affiche que sous un type où elle a un sens : le
    // serveur l'efface quand le type change, le moteur ne la lit pas ailleurs.
    affectationApplicable(monument) && typeof monument.affecteAuCulte === 'boolean' && {
      label: 'Affectation au culte',
      value: monument.affecteAuCulte ? 'Toujours affecté au culte' : 'Désaffecté',
    },
    architectureRomaneApplicable(monument) && typeof monument.architectureRomane === 'boolean' && {
      label: 'Architecture romane',
      value: monument.architectureRomane ? 'Oui, en tout ou en partie' : 'Non',
    },
    monument.siecleConstruction && {
      label: 'Siècle de construction',
      // Les données Mérimée arrivent parfois sous la forme « 12e s.;13e s. ».
      value: monument.siecleConstruction.split(';').map((s) => s.trim()).filter(Boolean).join(' · '),
    },
    proprietairesLibelles.length > 0 && {
      label: proprietairesLibelles.length > 1 ? 'Propriétaires' : 'Propriétaire',
      value: proprietairesLibelles,
    },
  ] as (FaitFiche | false | '' | undefined)[]).filter((f): f is FaitFiche => Boolean(f));

  return (
    <div className="fm">
      <div className="sec-h">
        <div>
          <h2>La fiche du monument</h2>
          <p>Ce qui décrit le bien. Elle vaut pour tous vos projets sur ce monument.</p>
        </div>
        {canEdit && (
          <button type="button" className="btn b-line b-sm" onClick={onEdit}>
            <Picto nom="crayon" />
            Modifier la fiche
          </button>
        )}
      </div>

      <section className="fm-statuts" aria-label="Protection et état sanitaire">
        <Statut
          titre="Protection"
          enonce={PROTECTION_ENONCE[monument.protection]
            ?? PROTECTION_LABELS[monument.protection]
            ?? monument.protection}
          note={dateArrete}
          phrase={PROTECTION_PHRASE[monument.protection] ?? ''}
        />
        <Statut
          titre="État sanitaire"
          enonce={enPeril === null ? 'État non renseigné' : (perilLabel(monument.etatConservation) ?? '')}
          phrase={enPeril === null ? PERIL_PHRASE.inconnu : enPeril ? PERIL_PHRASE.oui : PERIL_PHRASE.non}
          ton={enPeril === null ? 'inconnu' : enPeril ? 'alerte' : 'ok'}
        />
      </section>

      {faits.length > 0 && (
        <section className="fm-carte" aria-labelledby="fm-id">
          <h3 id="fm-id">Identification</h3>
          <dl className="fm-faits">
            {faits.map((f) => <Fait key={f.label} label={f.label} value={f.value} />)}
          </dl>
        </section>
      )}

      {monument.descriptionGenerale && (
        <section className="fm-carte" aria-labelledby="fm-desc">
          <h3 id="fm-desc">Description</h3>
          <Description text={monument.descriptionGenerale} />
        </section>
      )}

      {galerie.length > 0 && (
        <section className="fm-carte" aria-labelledby="fm-photos">
          <h3 id="fm-photos">Photos</h3>
          <div className="fm-galerie">
            {galerie.map((p) => (
              <figure key={p.url}>
                <div className="fm-img">
                  <img src={p.signedUrl} alt={p.legende || monument.nom} loading="lazy" />
                </div>
                {(p.legende || PHOTO_TYPE_LABELS[p.type]) && (
                  <figcaption>
                    {PHOTO_TYPE_LABELS[p.type] && <b>{PHOTO_TYPE_LABELS[p.type]}</b>}
                    {p.legende && <span>{PHOTO_TYPE_LABELS[p.type] ? ', ' : ''}{p.legende}</span>}
                  </figcaption>
                )}
              </figure>
            ))}
          </div>
        </section>
      )}

      <div className="fm-pied">
        <p>
          Fiche créée le {formatDate(monument.createdAt)}, modifiée le {formatDate(monument.updatedAt)}.
        </p>
        {canDelete && (
          <button type="button" className="btn b-sm fm-suppr" onClick={onDelete} disabled={deleting}>
            {deleting ? <Loader2 className="i animate-spin" /> : <IconSupprimer className="i" strokeWidth={1.8} />}
            Supprimer le monument
          </button>
        )}
      </div>
    </div>
  );
}
