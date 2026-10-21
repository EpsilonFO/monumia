import { useTranslation } from 'react-i18next';
import { Ico } from './Ico';
import { Repli } from './Repli';
import type { PieceAffichee } from '@/lib/fiche-aide';

/**
 * « Ce qu'il faut réunir ». Le bouton « Ajouter » mène au dossier, où se font
 * les dépôts : ouvert s'il existe, créé sinon. Un dossier est une ligne en base,
 * c'est pour cela qu'il ne se crée qu'à ce geste, et pas à l'arrivée sur la page.
 * Repliée par défaut ; la barre collante (« Réunir les pièces ») la déplie.
 */
export function FichePieces({
  pieces,
  onAjouter,
  ouverture,
}: {
  pieces: PieceAffichee[];
  onAjouter: () => void;
  ouverture: boolean;
}) {
  const { t } = useTranslation(['aide', 'common']);
  if (!pieces.length) return null;
  const obligatoires = pieces.filter((p) => p.obligatoire);
  const selonCas = pieces.filter((p) => !p.obligatoire);
  const faites = obligatoires.filter((p) => p.deposee).length;

  const ligne = (p: PieceAffichee) => (
    <div key={p.cle} className={`piece${p.obligatoire ? '' : ' opt'}${p.deposee ? ' done' : ''}`}>
      <span className="dot"><Ico nom="coche" /></span>
      <div>
        <b>{p.nom}</b>
        {(p.note || p.url) && (
          <small>
            {p.note}
            {p.note && p.url && ' '}
            {p.url && <a href={p.url} target="_blank" rel="noopener noreferrer">{t('common:actions.telecharger')}</a>}
          </small>
        )}
      </div>
      <button
        className="btn btn-line btn-sm"
        type="button"
        disabled={p.deposee || ouverture}
        onClick={onAjouter}
      >
        {p.deposee ? t('FichePieces.ajoutee') : t('common:actions.ajouter')}
      </button>
    </div>
  );

  return (
    <Repli
      id="pieces"
      className="repli-bloc"
      titre={t('FichePieces.titre')}
      ouvertParDefaut
      entete={
        <div className="block-head">
          <h2>{t('FichePieces.titre')}</h2>
          {obligatoires.length > 0 && (
            <span className="meta">
              {t('FichePieces.obligatoires', { faites, count: obligatoires.length })}
            </span>
          )}
        </div>
      }
    >
      <div className="card">
        {obligatoires.length > 0 && <div className="pieces">{obligatoires.map(ligne)}</div>}
        {selonCas.length > 0 && (
          <details className="opt-wrap" open={obligatoires.length === 0}>
            <summary>
              {t('FichePieces.selonSituation', { count: selonCas.length })}
            </summary>
            {selonCas.map(ligne)}
          </details>
        )}
        {obligatoires.length > 0 && (
          <div className="bar"><i style={{ width: `${(faites / obligatoires.length) * 100}%` }} /></div>
        )}
        <div className="pieces-foot"><span>{t('FichePieces.pied')}</span></div>
      </div>
    </Repli>
  );
}
