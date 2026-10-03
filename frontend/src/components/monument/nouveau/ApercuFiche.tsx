import { Loader2 } from 'lucide-react';
import { Picto } from '@/components/shared/ecrans/Picto';
import { ETAT_LABELS } from '@/constants/monument-options';
import {
  GROUPES_PROTECTION,
  libelleChoix,
  libellesProprietaires,
  libellesTypesEdifice,
  phraseManquants,
  pourcentageRempli,
  type FicheMonument,
} from '@/lib/fiche-monument';

interface ApercuFicheProps {
  fiche: FicheMonument;
  saving: boolean;
  onValider: () => void;
}

/**
 * L'aperçu « Fiche monument » à droite du formulaire : ce qui a été saisi, la
 * jauge, et le bouton qui enregistre.
 *
 * Le bouton mène au wizard PROJET, pas aux aides : un monument sans chantier ne
 * donne aucun diagnostic (cf. `MonumentWizardPage`). Son libellé le dit.
 */
export function ApercuFiche({ fiche, saving, onValider }: ApercuFicheProps) {
  const pct = pourcentageRempli(fiche);
  const manque = phraseManquants(fiche);
  const nom = fiche.nom?.trim();
  const commune = fiche.commune?.trim();

  const lignes: { titre: string; valeur: React.ReactNode }[] = [
    { titre: 'Type', valeur: libellesTypesEdifice(fiche).join(', ') || null },
    { titre: 'Construit au', valeur: fiche.siecleConstruction?.trim() || null },
    { titre: 'État', valeur: fiche.etatConservation ? ETAT_LABELS[fiche.etatConservation] : null },
    {
      titre: 'Protection',
      valeur: fiche.protection ? (
        <span className="pl">{libelleChoix(GROUPES_PROTECTION, fiche.protection)}</span>
      ) : null,
    },
    {
      titre: 'Propriétaire',
      valeur: libellesProprietaires(fiche).length ? (
        <span className="pl">{libellesProprietaires(fiche).join(', ')}</span>
      ) : null,
    },
  ];

  return (
    <aside className="side" aria-label="Aperçu de la fiche monument">
      <div className="pass">
        <div className="pass-h">
          <span className="k">Fiche monument</span>
          <h3 className={nom ? undefined : 'empty'}>{nom || 'Nom du bâtiment'}</h3>
          <p>
            {commune}
            {commune && fiche.departement ? ` (${fiche.departement})` : ''}
          </p>
          <div className="meter">
            <div className="t">
              <span>Fiche remplie</span>
              <span>{pct} %</span>
            </div>
            <div
              className="tr"
              role="progressbar"
              aria-label="Fiche remplie"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={pct}
            >
              <i style={{ width: `${pct}%` }} />
            </div>
          </div>
        </div>
        <dl>
          {lignes.map(({ titre, valeur }) => (
            <div key={titre}>
              <dt>{titre}</dt>
              <dd className={valeur ? undefined : 'no'}>{valeur || 'À renseigner'}</dd>
            </div>
          ))}
        </dl>
        <div className="pass-f">
          <button
            className="btn b-orange"
            type="button"
            disabled={manque !== null || saving}
            onClick={onValider}
          >
            {saving ? (
              <>
                <Loader2 className="i animate-spin" aria-hidden="true" />
                Enregistrement…
              </>
            ) : (
              <>
                Continuer vers mon projet
                <Picto nom="fleche" />
              </>
            )}
          </button>
          <small aria-live="polite">
            {manque ?? 'Ensuite, vous décrivez votre projet de travaux, puis Monumia trie les aides.'}
          </small>
        </div>
      </div>
      <p className="note">Vous pourrez tout modifier plus tard depuis la fiche du monument.</p>
    </aside>
  );
}
