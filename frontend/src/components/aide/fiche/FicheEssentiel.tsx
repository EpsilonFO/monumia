import { Ico, type NomIco } from './Ico';
import {
  CLASSE_GUICHET,
  dateLongue,
  lierContacts,
  libelleType,
  montantAide,
  type Guichet,
} from '@/lib/fiche-aide';
import type { Aide, AideTexteValeur, LigneEssentiel } from '@/types';

const TEINTE_CALENDRIER: Record<Guichet['etat'], string> = {
  ouvert: 't-green',
  bientot: 't-orange',
  clos: 't-red',
  attente: 't-sand',
};

const LIGNES: { cle: LigneEssentiel; libelle: string; ico: NomIco; teinte: string }[] = [
  { cle: 'financeur', libelle: "Qui verse l'aide", ico: 'financeur', teinte: 't-blue' },
  { cle: 'beneficiaires', libelle: 'Pour qui', ico: 'maison', teinte: 't-gold' },
  { cle: 'type', libelle: "Type d'aide", ico: 'document', teinte: 't-sand' },
  { cle: 'calendrier', libelle: "Jusqu'à quand", ico: 'calendrier', teinte: '' },
  { cle: 'delai', libelle: 'Délai de réponse', ico: 'delai', teinte: 't-blue' },
  { cle: 'depot', libelle: 'Comment déposer', ico: 'depot', teinte: 't-orange' },
  { cle: 'cumul', libelle: 'Cumul', ico: 'cumul', teinte: 't-gold' },
  { cle: 'contact', libelle: 'Contact', ico: 'contact', teinte: 't-blue' },
];

/**
 * La valeur de chaque ligne. La fiche rédigée d'abord ; sans elle, ce que les
 * champs bruts savent dire. Le calendrier fait exception : sa valeur vient
 * toujours des dates (cf. `guichet`).
 */
/** « Non précisé par la source » n'est pas un délai : la ligne ne s'affiche pas. */
const NON_PRECISE = /^non (précisé|indiqué|communiqué)/i;

function lignesDe(aide: Aide, g: Guichet): Partial<Record<LigneEssentiel, AideTexteValeur>> {
  const ecrit = aide.fiche?.essentiel ?? {};
  const delaiBrut = aide.delaiInstruction && !NON_PRECISE.test(aide.delaiInstruction.trim())
    ? aide.delaiInstruction
    : null;
  return {
    financeur: ecrit.financeur ?? (aide.organisme ? { valeur: aide.organisme } : undefined),
    beneficiaires: ecrit.beneficiaires,
    type: { ...ecrit.type, valeur: libelleType(aide) },
    calendrier: { detail: ecrit.calendrier?.detail, valeur: g.valeur },
    delai: ecrit.delai ?? (delaiBrut ? { valeur: delaiBrut } : undefined),
    depot: ecrit.depot,
    cumul: ecrit.cumul,
    contact: ecrit.contact ?? (aide.organismeContact ? { valeur: aide.organismeContact } : undefined),
  };
}

function AvecLiens({ texte }: { texte: string }) {
  return (
    <>
      {lierContacts(texte).map((m, i) =>
        m.lien ? <a key={i} href={m.lien}>{m.texte}</a> : <span key={i}>{m.texte}</span>,
      )}
    </>
  );
}

export function FicheEssentiel({
  aide,
  guichet: g,
  onSignaler,
}: {
  aide: Aide;
  guichet: Guichet;
  /** Absent quand aucun canal de signalement n'est branché : le lien disparaît. */
  onSignaler?: () => void;
}) {
  const montant = montantAide(aide);
  const lignes = lignesDe(aide, g);

  return (
    <>
      <div className="ess">
        <div className="ess-h" data-guide="aide.montant">
          <p className="ess-k">
            <span id="ess-t">L'essentiel</span>
            <span className={`status on-blue ${CLASSE_GUICHET[g.etat]}`}><i />{g.court}</span>
          </p>
          <p className="ess-amt">{montant?.valeur ?? 'Montant non publié'}</p>
          {montant?.detail && <p className="ess-amt-s">{montant.detail}</p>}
        </div>
        <div className="ess-b">
          {LIGNES.map(({ cle, libelle, ico, teinte }) => {
            const ligne = lignes[cle];
            if (!ligne?.valeur) return null;
            return (
              <div key={cle} className="ess-row">
                <span className={`chip sm ${cle === 'calendrier' ? TEINTE_CALENDRIER[g.etat] : teinte}`}>
                  <Ico nom={ico} />
                </span>
                <div>
                  <small>{libelle}</small>
                  <b>{cle === 'contact' ? <AvecLiens texte={ligne.valeur} /> : ligne.valeur}</b>
                  {ligne.detail && <span>{ligne.detail}</span>}
                </div>
              </div>
            );
          })}
        </div>
        {(aide.urlOfficielle || aide.formulaireUrl) && (
          <div className="ess-f">
            {aide.urlOfficielle && (
              <a className="btn btn-ess" href={aide.urlOfficielle} target="_blank" rel="noopener noreferrer">
                <Ico nom="externe" />Page officielle
              </a>
            )}
            {aide.formulaireUrl && (
              <a className="btn btn-ess" href={aide.formulaireUrl} target="_blank" rel="noopener noreferrer">
                <Ico nom="formulaire" />Formulaire
              </a>
            )}
          </div>
        )}
      </div>
      {(aide.verifieLe || onSignaler) && (
        <p className="checked">
          {aide.verifieLe && <>Vérifié par Monumia le {dateLongue(aide.verifieLe)}</>}
          {aide.verifieLe && onSignaler && ' · '}
          {onSignaler && <button type="button" onClick={onSignaler}>Signaler une erreur</button>}
        </p>
      )}
    </>
  );
}
