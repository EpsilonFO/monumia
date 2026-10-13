import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { Picto } from '@/components/shared/ecrans/Picto';
import { ROUTES } from '@/constants/routes';
import { projetTitre } from '@/lib/projet-titre';
import { projectPermissions } from '@/lib/project-permissions';
import type { Monument, Projet } from '@/types';

interface ProjetSummaryBarProps {
  projet: Projet;
  /** Monument parent : rappelé au-dessus du titre. Les DROITS, eux, viennent du projet. */
  monument: Monument;
  onRefaireQuestionnaire: () => void;
  /** Questions passées sans réponse : ce que « Modifier mes réponses » peut
   *  reprendre sans rien effacer. */
  questionsPassees: number;
  /** Renomme le projet. Doit lever si l'enregistrement échoue : l'en-tête reste
   *  alors en édition, la saisie de l'utilisateur n'est jamais perdue. */
  onRenommer: (titre: string) => Promise<void>;
}

/**
 * En-tête de la page projet (maquette `monumia-page-aides.html`) : le monument
 * en lien bleu, le nom du chantier et son crayon, et à droite « Modifier mes
 * réponses ». L'identité du bien (protection, état sanitaire, équipe) reste sur
 * la page du monument.
 */
export function ProjetSummaryBar({
  projet,
  monument,
  onRefaireQuestionnaire,
  questionsPassees,
  onRenommer,
}: ProjetSummaryBarProps) {
  const perms = projectPermissions(projet.myRole ?? null);
  const peutEditer = perms.canEditProject;
  // Liste vide = « Pas encore déterminé » : aucune aide n'est filtrée sur le
  // type de travaux, et il faut que ça se voie.
  const travauxIndetermines = (projet.travauxEnvisages ?? []).length === 0;

  // Renommage EN PLACE : le champ prend exactement la place du titre, sans
  // fenêtre par-dessus. On part de ce qui est affiché — titre saisi ou libellé
  // déduit des travaux — pour que l'on édite bien ce que l'on voit.
  const titreAffiche = projetTitre(projet, monument.nom);
  const [edition, setEdition] = useState(false);
  const [saisie, setSaisie] = useState(titreAffiche);
  const [enregistrement, setEnregistrement] = useState(false);
  const champRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (edition) champRef.current?.select();
  }, [edition]);

  function ouvrirEdition() {
    setSaisie(titreAffiche);
    setEdition(true);
  }

  async function valider() {
    const titre = saisie.trim();
    // Au moins un caractère : un titre vide ne remplace jamais celui en place.
    if (!titre) return;
    if (titre === titreAffiche) {
      setEdition(false);
      return;
    }
    setEnregistrement(true);
    try {
      await onRenommer(titre);
      setEdition(false);
    } catch {
      // L'erreur est signalée par l'appelant : on reste en édition.
    } finally {
      setEnregistrement(false);
    }
  }

  return (
    <section className="phead" aria-labelledby="pt">
      <div>
        <Link className="lieu" to={`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=projets`}>
          {monument.nom}
        </Link>
        {edition ? (
          <>
            <input
              ref={champRef}
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void valider();
                if (e.key === 'Escape') setEdition(false);
              }}
              // Sortir du champ vaut validation, sauf si la saisie est vide :
              // on revient alors au titre en place plutôt que de bloquer.
              onBlur={() => (saisie.trim() ? void valider() : setEdition(false))}
              disabled={enregistrement}
              aria-label="Nom du projet"
              autoFocus
              className={saisie.trim() ? 'renommer' : 'renommer vide'}
            />
            <p className="aide-saisie">
              {saisie.trim()
                ? 'Entrée pour valider, Échap pour annuler.'
                : 'Le nom doit contenir au moins un caractère.'}
            </p>
          </>
        ) : (
          <h1 id="pt">
            {titreAffiche}
            {peutEditer && (
              <button
                className="edit"
                type="button"
                onClick={ouvrirEdition}
                aria-label="Renommer le projet"
                title="Renommer le projet"
              >
                <Picto nom="crayon" />
              </button>
            )}
            {travauxIndetermines && <span className="clos">Travaux pas encore déterminés</span>}
            {projet.clotureAt && <span className="clos">Clôturé</span>}
          </h1>
        )}
      </div>
      {perms.canAccessAides && (
        <div className="proj-act">
          <button
            className="btn b-line"
            type="button"
            onClick={onRefaireQuestionnaire}
            data-guide="projet.refaire"
          >
            <Picto nom="refaire" />
            Modifier mes réponses
          </button>
          {questionsPassees > 0 && (
            <small>
              {questionsPassees === 1
                ? '1 question passée, à reprendre sans rien effacer'
                : `${questionsPassees} questions passées, à reprendre sans rien effacer`}
            </small>
          )}
        </div>
      )}
    </section>
  );
}
