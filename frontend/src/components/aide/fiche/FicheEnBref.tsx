import { useTranslation } from 'react-i18next';
import { Ico, type NomIco } from './Ico';
import { decodeHtml } from '@/components/aide/AideDetails';
import type { Guichet } from '@/lib/fiche-aide';
import type { Aide, TonEnBref } from '@/types';

const PUCE: Record<TonEnBref, { ico: NomIco; teinte: string }> = {
  couvert: { ico: 'coche', teinte: 't-green' },
  montant: { ico: 'montant', teinte: 't-orange' },
  exclu: { ico: 'croix', teinte: 't-red' },
  calendrier: { ico: 'calendrier', teinte: 't-gold' },
  info: { ico: 'info', teinte: 't-blue' },
};

/** Le dépôt n'est pas possible aujourd'hui, ou le règlement ne dit pas quand. */
export function FicheBandeauGuichet({ guichet: g }: { guichet: Guichet }) {
  if (!g.bandeau) return null;
  const clos = g.etat === 'clos';
  return (
    <div className={clos ? 'closed' : 'closed wait'}>
      <span className={`chip ${clos ? 't-solid-red' : 't-sand'}`}><Ico nom="cloche" /></span>
      <div>
        <b>{g.bandeau.titre}</b>
        <p>{g.bandeau.texte}</p>
      </div>
    </div>
  );
}

/**
 * Trois puces, puis le détail replié. Sans fiche rédigée, la description longue
 * en tient lieu, découpée en paragraphes : c'est le seul texte de synthèse que
 * l'ingestion produit.
 */
export function FicheEnBref({ aide }: { aide: Aide }) {
  const { t } = useTranslation('aide');
  const ecrit = aide.fiche?.enBref;
  const puces = ecrit?.puces ?? [];
  const detail = ecrit?.detail.length
    ? ecrit.detail
    : decodeHtml(aide.descriptionLongue || '').split(/\n+/).map((p) => p.trim()).filter(Boolean);
  if (!puces.length && !detail.length) return null;

  return (
    <section className="bref" aria-labelledby="bref-t">
      <h2 id="bref-t">{t('FicheEnBref.titre')}</h2>
      {puces.length > 0 ? (
        <>
          <ul>
            {puces.map((p, i) => (
              <li key={i}>
                <span className={`chip xs ${PUCE[p.ton].teinte}`}><Ico nom={PUCE[p.ton].ico} /></span>
                <p>{p.texte}</p>
              </li>
            ))}
          </ul>
          {detail.length > 0 && (
            <details className="more">
              <summary>{t('FicheEnBref.lireDetail')}</summary>
              {detail.map((p, i) => <p key={i}>{p}</p>)}
            </details>
          )}
        </>
      ) : (
        <div className="more plain">
          {detail.map((p, i) => <p key={i}>{p}</p>)}
        </div>
      )}
    </section>
  );
}
