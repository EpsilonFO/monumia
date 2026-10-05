import { useState } from 'react';

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
  const [masquee, setMasquee] = useState(masqueeMemorisee);
  const basculer = (m: boolean) => {
    setMasquee(m);
    memoriser(m);
  };

  if (masquee) {
    return (
      <button className="why-open" type="button" onClick={() => basculer(false)}>
        Comment fonctionne cet espace&nbsp;?
      </button>
    );
  }

  return (
    <section className="why" aria-labelledby="why-t">
      <div className="why-h">
        <div>
          <h2 id="why-t">Comment fonctionne cet espace</h2>
          <p>Vous y rangez les pièces de votre monument. Elles servent ensuite pour vos dossiers d&rsquo;aide.</p>
        </div>
        <button className="why-x" type="button" onClick={() => basculer(true)}>
          Masquer
        </button>
      </div>
      <ol className="why-steps">
        <li>
          <span className="n">1</span>
          <div>
            <b>Vous ajoutez un document</b>
            <p>Vous le classez dans le dossier qui lui correspond&nbsp;: Devis, Arrêtés, Délibérations, Photos…</p>
          </div>
        </li>
        <li>
          <span className="n">2</span>
          <div>
            <b>Vous le réutilisez dans vos dossiers</b>
            <p>Quand une aide demande cette pièce, vous la prenez ici au lieu de la chercher sur votre ordinateur.</p>
          </div>
        </li>
        <li>
          <span className="n">3</span>
          <div>
            <b>Vous gardez la main</b>
            <p>
              Seuls vous et les personnes que vous invitez y ont accès. Monumia n&rsquo;envoie rien aux
              financeurs&nbsp;: c&rsquo;est vous qui déposez vos dossiers.
            </p>
          </div>
        </li>
      </ol>
    </section>
  );
}
