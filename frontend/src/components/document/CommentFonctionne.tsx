import { useState } from 'react';
import { useTranslation } from 'react-i18next';

/** Masqué une fois : une commodité du navigateur, jamais une donnée. */
const CLE = 'monumia.documents.explication-masquee';

function masqueeMemorisee(): boolean {
  try { return window.localStorage.getItem(CLE) === '1'; } catch { return false; }
}

function memoriser(masquee: boolean) {
  try {
    if (masquee) window.localStorage.setItem(CLE, '1');
    else window.localStorage.removeItem(CLE);
  } catch {
    // Stockage indisponible (navigation privée) : le choix vaut pour la visite.
  }
}

/**
 * L'encadré « Comment fonctionne cet espace » de Mes documents (maquette
 * `monumia-documents.html`) : trois étapes, et « Masquer » qui le réduit à un
 * lien pour le rouvrir.
 */
export function CommentFonctionne() {
  const { t } = useTranslation('documents');
  const [masquee, setMasquee] = useState(masqueeMemorisee);
  const basculer = (m: boolean) => {
    setMasquee(m);
    memoriser(m);
  };

  if (masquee) {
    return (
      <button className="why-open" type="button" onClick={() => basculer(false)}>
        {t('CommentFonctionne.ouvrir')}
      </button>
    );
  }

  return (
    <section className="why" aria-labelledby="why-t">
      <div className="why-h">
        <div>
          <h2 id="why-t">{t('CommentFonctionne.titre')}</h2>
          <p>{t('CommentFonctionne.intro')}</p>
        </div>
        <button className="why-x" type="button" onClick={() => basculer(true)}>
          {t('CommentFonctionne.masquer')}
        </button>
      </div>
      <ol className="why-steps">
        <li>
          <span className="n">1</span>
          <div>
            <b>{t('CommentFonctionne.etape1Titre')}</b>
            <p>{t('CommentFonctionne.etape1Texte')}</p>
          </div>
        </li>
        <li>
          <span className="n">2</span>
          <div>
            <b>{t('CommentFonctionne.etape2Titre')}</b>
            <p>{t('CommentFonctionne.etape2Texte')}</p>
          </div>
        </li>
        <li>
          <span className="n">3</span>
          <div>
            <b>{t('CommentFonctionne.etape3Titre')}</b>
            <p>{t('CommentFonctionne.etape3Texte')}</p>
          </div>
        </li>
      </ol>
    </section>
  );
}
