import { Link } from 'react-router';
import { format, parseISO } from 'date-fns';
import { fr } from 'date-fns/locale';
import { Picto } from '@/components/shared/ecrans/Picto';
import { deadlineLink } from '@/lib/project-stats';
import { quandLibelle, type AFaire } from '@/lib/a-faire-maintenant';

/** Le bouton et la bande « Prochaine étape », selon ce qu'il reste à faire. */
function suite(a: AFaire): { cta: string; etape: React.ReactNode } {
  switch (a.nature) {
    case 'questions': {
      const n = a.questions;
      return {
        cta: n === 1 ? 'Répondre à la question' : `Répondre aux ${n} questions`,
        etape: (
          <>
            <b>{n === 1 ? '1 question' : `${n} questions`}</b> pour savoir si vous pouvez déposer. Ensuite, Monumia
            vous indique les pièces à réunir.
          </>
        ),
      };
    }
    case 'verifier':
      return {
        cta: "Voir l'aide",
        etape: <>Quelques points sont à vérifier sur la fiche de l'aide avant de déposer.</>,
      };
    case 'eligible':
      return {
        cta: 'Voir les pièces à réunir',
        etape: (
          <>
            <b>Votre projet remplit les conditions publiées.</b> Monumia vous indique les pièces à réunir.
          </>
        ),
      };
    case 'demarche':
      return {
        cta: 'Voir la démarche',
        etape: (
          <>
            <b>Une démarche à faire</b> avant le dépôt pour remplir les conditions de l'aide.
          </>
        ),
      };
    case 'dossier':
      return {
        cta: 'Ouvrir le dossier',
        etape: (
          <>
            <b>{a.detail}</b> : l'échéance de votre dossier.
          </>
        ),
      };
  }
}

/**
 * « À faire maintenant » : la date la plus proche, en éphéméride orange, ce
 * qu'elle concerne, et la bande bleue qui dit la prochaine étape. Toute la
 * carte mène où mène son bouton (`.now-lien::after`).
 */
export function AFaireMaintenantCarte({ aFaire }: { aFaire: AFaire | null }) {
  if (!aFaire) {
    return (
      <section className="now calme" aria-labelledby="nowT">
        <div className="now-in">
          <div>
            <span className="tag-now">Tout est à jour</span>
            <h2 id="nowT">Aucune date limite ne réclame votre attention pour le moment.</h2>
          </div>
        </div>
      </section>
    );
  }

  const { echeance } = aFaire;
  const date = parseISO(echeance.date);
  const retard = echeance.joursRestants < 0;
  const { cta, etape } = suite(aFaire);
  const sousTitre = [aFaire.monumentNom, aFaire.nature === 'dossier' ? null : aFaire.detail].filter(Boolean);

  return (
    <section className="now" aria-labelledby="nowT">
      <div className="now-in">
        <div className={retard ? 'cal retard' : 'cal'} aria-hidden="true">
          <b>{format(date, 'd', { locale: fr })}</b>
          <span>{format(date, 'MMM', { locale: fr })}</span>
        </div>
        <div>
          <span className={retard ? 'tag-now retard' : 'tag-now'}>
            À faire maintenant · {quandLibelle(echeance.joursRestants)}
          </span>
          <h2 id="nowT">{aFaire.titre}</h2>
          {(aFaire.montant || sousTitre.length > 0) && (
            <p className="sub">
              {aFaire.montant && <b>{aFaire.montant}</b>}
              {aFaire.montant && sousTitre.length > 0 && ' · '}
              {sousTitre.join(' · ')}
            </p>
          )}
        </div>
        <Link className="btn b-orange now-lien" to={deadlineLink(echeance)}>
          {cta}
          <Picto nom="fleche" />
        </Link>
      </div>
      <div className="now-step">
        <span className="lbl">Prochaine étape</span>
        <span>{etape}</span>
      </div>
    </section>
  );
}
