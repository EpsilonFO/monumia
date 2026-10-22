import { Trans, useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import type { TFunction } from 'i18next';
import { Picto } from '@/components/shared/ecrans/Picto';
import { PictoDossierPlein } from '@/components/document/PictosDocuments';
import { ROUTES } from '@/constants/routes';
import { libelleEtape, rangEnCours } from '@/lib/avancement';
import { monumentPhotoProfil } from '@/lib/monument-photo';
import { PROJECT_STAGES, type MonumentStats, type ProjectStage } from '@/lib/project-stats';
import { monumentNomCourt, projetSousTitre, projetTitre } from '@/lib/projet-titre';
import type { Monument, Projet } from '@/types';
import './carte-monument.css';

/** « 1 document prêt pour vos dossiers » : les pièces du monument et de ses projets. */
function phraseDocuments(n: number, t: TFunction<'dashboard'>): string {
  return n > 0
    ? t('CarteMonument.documentsPrets', { count: n })
    : t('CarteMonument.aucunDocument');
}

/** Un projet du monument : son titre, ses travaux, ses étapes en points, une ligne qui mène au projet. */
function LigneProjet({ projet, monumentNom, stage }: { projet: Projet; monumentNom: string; stage: ProjectStage }) {
  const { t } = useTranslation('dashboard');
  const titre = projetTitre(projet, monumentNom);
  const sous = projetSousTitre(projet, monumentNom);
  const rang = rangEnCours(stage);
  const etape = libelleEtape(stage);
  const statut = projet.clotureAt
    ? t('CarteMonument.cloture')
    : t('CarteMonument.statut', { rang: etape.rang, action: etape.action });
  return (
    <Link className="pr" to={ROUTES.PROJET_DETAIL(projet.id)}>
      <span className="pr-t">
        <b>{titre}</b>
        {sous && <small>{sous}</small>}
      </span>
      <span className="pr-s">
        <span className="dots" aria-hidden="true">
          {PROJECT_STAGES.map((s, i) => <i key={s.key} className={i <= rang ? 'on' : undefined} />)}
        </span>
        {statut}
      </span>
      <Picto nom="fleche" className="i pr-a" />
    </Link>
  );
}

/**
 * Un monument sur le tableau de bord et dans « Mes monuments » (maquettes
 * `monumia-tableau-de-bord.html` et `monumia-mes-monuments.html`) : sa photo en
 * bannière (la bande bleue à défaut), son nom dessus, puis la liste de ses
 * projets, chacun avec ses étapes. Le pied diffère : le tableau de bord compte
 * les aides repérées, « Mes monuments » (`variante="liste"`) ouvre ses
 * documents. Sur les deux, « Lancer une nouvelle recherche » quand la page
 * montre plusieurs monuments (`onNouvelleRecherche`) ; avec un seul, c'est la
 * carte en pointillé sous la liste qui le propose. Toute la carte mène à ses
 * projets : le lien « Voir les projets » s'étend sur la carte
 * (`.cmon-lien::after`), les lignes de projet et les autres boutons passent
 * au-dessus.
 */
export function CarteMonument({
  monument,
  projets,
  stats,
  etapeDe,
  nbDocuments,
  variante = 'tableau',
  onNouvelleRecherche,
}: {
  monument: Monument;
  projets: Projet[];
  stats: MonumentStats | undefined;
  etapeDe: (projet: Projet) => ProjectStage;
  /** Documents du monument et de ses projets, tels que le serveur les rend. */
  nbDocuments: number;
  variante?: 'tableau' | 'liste';
  /** « Lancer une nouvelle recherche » sur ce monument. Absent : pas de bouton
   *  (un seul monument sur la page, ou droits d'équipe insuffisants). */
  onNouvelleRecherche?: () => void;
}) {
  const { t } = useTranslation('dashboard');
  const lieu = [monument.commune, monument.departement].filter(Boolean).join(', ');
  const photo = monumentPhotoProfil(monument)?.signedUrl ?? null;
  const aides = stats?.aidesIdentifiees ?? 0;
  const enCours = projets.filter((p) => !p.clotureAt).length;
  // Les chantiers ouverts d'abord, puis les clôturés ; à l'intérieur, l'ordre du store.
  const lignes = [...projets].sort((a, b) => Number(!!a.clotureAt) - Number(!!b.clotureAt));
  // `monumentNomCourt` rend null hors du français : la phrase retombe sur « de ce monument ».
  const deNomCourt = monumentNomCourt(monument.nom, true);

  const nouvelleRecherche = onNouvelleRecherche && (
    <button className="btn b-oline b-sm" type="button" onClick={onNouvelleRecherche}>
      <Picto nom="loupe" />
      {t('lancerRecherche')}
    </button>
  );

  const voir = (
    <Link className="btn b-blue b-sm cmon-lien" to={`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=projets`}>
      {projets.length > 0 ? t('CarteMonument.voirProjets') : t('voirMonument')}
      <Picto nom="fleche" />
    </Link>
  );

  return (
    <article className="cmon" data-guide="monuments.carte">
      <div
        className={photo ? 'cmon-h photo' : 'cmon-h'}
        style={photo ? { backgroundImage: `var(--cmon-voile), url("${photo}")` } : undefined}
      >
        <h3>{monument.nom}</h3>
        {lieu && <p>{lieu}</p>}
      </div>
      <div className="cmon-b">
        <div className="projs">
          <span className="projs-k">
            {enCours > 0
              ? t('CarteMonument.projetsEnCours', { count: enCours })
              : projets.length > 0
                ? t('CarteMonument.aucunProjetEnCours')
                : t('CarteMonument.pasEncoreDeProjet')}
          </span>
          {lignes.map((p) => (
            <LigneProjet key={p.id} projet={p} monumentNom={monument.nom} stage={etapeDe(p)} />
          ))}
        </div>
        {variante === 'tableau' ? (
          <div className="cmon-f">
            <span>
              {aides > 0 ? (
                <Trans t={t} i18nKey="CarteMonument.aidesReperees" count={aides} components={{ b: <b /> }} />
              ) : (
                t('CarteMonument.aucuneAide')
              )}
              <small className="hint">{phraseDocuments(nbDocuments, t)}</small>
            </span>
            <div className="acts">
              {nouvelleRecherche}
              {voir}
            </div>
          </div>
        ) : (
          <div className="cmon-f">
            <span className="hint">{phraseDocuments(nbDocuments, t)}</span>
            <div className="acts">
              <Link
                className="btn b-line b-sm"
                to={`${ROUTES.DOCUMENTS}?monument=${encodeURIComponent(monument.id)}`}
                title={
                  deNomCourt
                    ? t('CarteMonument.piecesTitre', { deNom: deNomCourt })
                    : t('CarteMonument.piecesTitreSansNom')
                }
              >
                <PictoDossierPlein className="i" />
                {t('CarteMonument.documents')} <em className="navc">{nbDocuments}</em>
              </Link>
              {nouvelleRecherche}
              {voir}
            </div>
          </div>
        )}
      </div>
    </article>
  );
}
