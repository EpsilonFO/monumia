import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { IconSupprimer } from '@/components/icons';
import { Picto } from '@/components/shared/ecrans/Picto';
import { formatDate } from '@/lib/date-utils';
import {
  PROTECTION_LABELS, isEnPeril, perilLabel,
} from '@/constants/monument-options';
import {
  affectationApplicable, libellesProprietaires, libellesTypesEdifice,
} from '@/lib/fiche-monument';
import type { Monument } from '@/types';

/* ------------------------------------------------------------------ */
/* Ce que disent les statuts                                           */
/* ------------------------------------------------------------------ */

// L'en-tête de la fiche énonce le statut comme le fait l'arrêté — « Classé au
// titre des monuments historiques », et non le libellé court des badges. C'est
// la seule page où il se lit en entier ; ailleurs la place manque. Sous la même
// clé, `protectionPhrase` dit ce que ce statut change pour le propriétaire.
const CLES_PROTECTION = {
  classe: 'classe',
  inscrit: 'inscrit',
  abords: 'abords',
  spr: 'spr',
  non_protege: 'nonProtege',
} as const;

function cleProtection(protection: string) {
  return Object.hasOwn(CLES_PROTECTION, protection)
    ? CLES_PROTECTION[protection as keyof typeof CLES_PROTECTION]
    : undefined;
}

const TYPES_PHOTO = ['facade', 'interieur', 'detail', 'aerien', 'degradation'] as const;

function estTypePhotoLibelle(type: string): type is (typeof TYPES_PHOTO)[number] {
  return (TYPES_PHOTO as readonly string[]).includes(type);
}

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
  const { t } = useTranslation('monuments');
  // La photo de profil illustre déjà l'en-tête : pas de doublon dans la galerie.
  // Sans lien signé, l'image serait cassée (bucket privé) : on l'écarte.
  const galerie = (monument.photos ?? []).filter((p) => p.type !== 'profil' && p.signedUrl);
  const enPeril = isEnPeril(monument.etatConservation);

  // Un bien non protégé peut garder d'anciennes dates en base : on ne les montre pas.
  const dateArrete = monument.protection !== 'non_protege' && monument.dateProtection
    ? t('MonumentFiche.arrete', { date: formatDate(monument.dateProtection) })
    : undefined;

  const typesLibelles = libellesTypesEdifice(monument);
  const proprietairesLibelles = libellesProprietaires(monument);
  const cle = cleProtection(monument.protection);
  const typePhoto = (type: string) =>
    estTypePhotoLibelle(type) ? t(`MonumentFiche.typePhoto.${type}`) : undefined;

  // Identification : seuls les champs renseignés apparaissent.
  type FaitFiche = { label: string; value: string | string[] };
  const faits = ([
    monument.commune && { label: t('MonumentFiche.commune'), value: monument.commune },
    monument.departement && { label: t('MonumentFiche.departement'), value: monument.departement },
    typesLibelles.length > 0 && {
      label: t('MonumentFiche.typesEdifice', { count: typesLibelles.length }),
      value: typesLibelles,
    },
    // Une précision ne s'affiche que sous un type où elle a un sens : le
    // serveur l'efface quand le type change, le moteur ne la lit pas ailleurs.
    affectationApplicable(monument) && typeof monument.affecteAuCulte === 'boolean' && {
      label: t('MonumentFiche.affectationCulte'),
      value: monument.affecteAuCulte
        ? t('MonumentFiche.toujoursAffecte')
        : t('MonumentFiche.desaffecte'),
    },
    monument.siecleConstruction && {
      label: t('MonumentFiche.siecleConstruction'),
      // Les données Mérimée arrivent parfois sous la forme « 12e s.;13e s. ».
      value: monument.siecleConstruction.split(';').map((s) => s.trim()).filter(Boolean).join(' · '),
    },
    proprietairesLibelles.length > 0 && {
      label: t('MonumentFiche.proprietaires', { count: proprietairesLibelles.length }),
      value: proprietairesLibelles,
    },
  ] as (FaitFiche | false | '' | undefined)[]).filter((f): f is FaitFiche => Boolean(f));

  return (
    <div className="fm">
      <div className="sec-h">
        <div>
          <h2>{t('MonumentFiche.titre')}</h2>
          <p>{t('MonumentFiche.sousTitre')}</p>
        </div>
        {canEdit && (
          <button type="button" className="btn b-line b-sm" onClick={onEdit}>
            <Picto nom="crayon" />
            {t('MonumentFiche.modifierFiche')}
          </button>
        )}
      </div>

      <section className="fm-statuts" aria-label={t('MonumentFiche.statutsAria')}>
        <Statut
          titre={t('MonumentFiche.protection')}
          enonce={cle
            ? t(`MonumentFiche.protectionEnonce.${cle}`)
            : (PROTECTION_LABELS[monument.protection] ?? monument.protection)}
          note={dateArrete}
          phrase={cle ? t(`MonumentFiche.protectionPhrase.${cle}`) : ''}
        />
        <Statut
          titre={t('MonumentFiche.etatSanitaire')}
          enonce={enPeril === null ? t('MonumentFiche.etatNonRenseigne') : (perilLabel(monument.etatConservation) ?? '')}
          phrase={t(`MonumentFiche.perilPhrase.${enPeril === null ? 'inconnu' : enPeril ? 'oui' : 'non'}`)}
          ton={enPeril === null ? 'inconnu' : enPeril ? 'alerte' : 'ok'}
        />
      </section>

      {faits.length > 0 && (
        <section className="fm-carte" aria-labelledby="fm-id">
          <h3 id="fm-id">{t('MonumentFiche.identification')}</h3>
          <dl className="fm-faits">
            {faits.map((f) => <Fait key={f.label} label={f.label} value={f.value} />)}
          </dl>
        </section>
      )}

      {monument.descriptionGenerale && (
        <section className="fm-carte" aria-labelledby="fm-desc">
          <h3 id="fm-desc">{t('MonumentFiche.descriptionProtection')}</h3>
          <Description text={monument.descriptionGenerale} />
        </section>
      )}

      {galerie.length > 0 && (
        <section className="fm-carte" aria-labelledby="fm-photos">
          <h3 id="fm-photos">{t('MonumentFiche.photos')}</h3>
          <div className="fm-galerie">
            {galerie.map((p) => {
              const libelleType = typePhoto(p.type);
              return (
              <figure key={p.url}>
                <div className="fm-img">
                  <img src={p.signedUrl} alt={p.legende || monument.nom} loading="lazy" />
                </div>
                {(p.legende || libelleType) && (
                  <figcaption>
                    {libelleType && <b>{libelleType}</b>}
                    {p.legende && <span>{libelleType ? ', ' : ''}{p.legende}</span>}
                  </figcaption>
                )}
              </figure>
              );
            })}
          </div>
        </section>
      )}

      <div className="fm-pied">
        <p>
          {t('MonumentFiche.dates', {
            creation: formatDate(monument.createdAt),
            modification: formatDate(monument.updatedAt),
          })}
        </p>
        {canDelete && (
          <button type="button" className="btn b-sm fm-suppr" onClick={onDelete} disabled={deleting}>
            {deleting ? <Loader2 className="i animate-spin" /> : <IconSupprimer className="i" strokeWidth={1.8} />}
            {t('MonumentFiche.supprimer')}
          </button>
        )}
      </div>
    </div>
  );
}
