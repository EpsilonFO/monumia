import { useEffect, useRef, useState } from 'react';
import { IconChantier, IconModifier, IconMonument, IconRafraichir } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { C, SERIF } from '@/lib/brand';
import { WORK_TYPES } from '@/constants/monument-options';
import { projetTitre } from '@/lib/projet-titre';
import { projectPermissions } from '@/lib/project-permissions';
import type { Monument, Projet } from '@/types';

interface ProjetSummaryBarProps {
  projet: Projet;
  /** Monument parent : rappelé sous le titre. Les DROITS, eux, viennent du projet. */
  monument: Monument;
  onRefaireQuestionnaire: () => void;
  /** Renomme le projet. Doit lever si l'enregistrement échoue : l'en-tête reste
   *  alors en édition, la saisie de l'utilisateur n'est jamais perdue. */
  onRenommer: (titre: string) => Promise<void>;
}

const WORK_LABELS = Object.fromEntries(WORK_TYPES.map((w) => [w.value, w.label]));

/**
 * En-tête de la page projet : le chantier. L'identité du bien (protection,
 * état sanitaire, équipe) reste sur la page du monument.
 */
export function ProjetSummaryBar({
  projet,
  monument,
  onRefaireQuestionnaire,
  onRenommer,
}: ProjetSummaryBarProps) {
  const travaux = projet.travauxEnvisages ?? [];
  const titreExplicite = !!projet.titre?.trim();
  const peutEditer = projectPermissions(projet.myRole ?? null).canEditProject;

  // Renommage EN PLACE : le champ prend exactement la place du titre, sans
  // fenêtre par-dessus. On part de ce qui est affiché — titre saisi ou libellé
  // déduit des travaux — pour que l'on édite bien ce que l'on voit.
  const titreAffiche = projetTitre(projet);
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
    <div
      className="rounded-2xl border p-6 sm:p-7"
      style={{ background: C.card, borderColor: C.border }}
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3 min-w-0">
          {edition ? (
            <div className="space-y-1.5">
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
                className="w-full rounded-lg border bg-transparent px-3 py-1 text-[clamp(1.5rem,3vw,2rem)] leading-tight outline-none focus:ring-[3px] disabled:opacity-60"
                style={{
                  fontFamily: SERIF,
                  color: C.ink,
                  borderColor: saisie.trim() ? C.border : C.orange,
                  boxShadow: 'none',
                }}
              />
              <p className="text-[12.5px] text-muted-foreground">
                {saisie.trim()
                  ? 'Entrée pour valider, Échap pour annuler.'
                  : 'Le nom doit contenir au moins un caractère.'}
              </p>
            </div>
          ) : (
            <div className="flex items-start gap-2">
              <h1
                className="min-w-0 text-[clamp(1.5rem,3vw,2rem)] leading-tight"
                style={{ fontFamily: SERIF, color: C.ink }}
              >
                {titreAffiche}
              </h1>
              {peutEditer && (
                <button
                  type="button"
                  onClick={ouvrirEdition}
                  aria-label="Renommer le projet"
                  title="Renommer le projet"
                  className="mt-1.5 shrink-0 rounded-md p-1 transition-colors hover:bg-muted"
                  style={{ color: C.grayFg }}
                >
                  <IconModifier className="h-4 w-4" />
                </button>
              )}
            </div>
          )}
          <div className="flex items-center gap-1.5 text-[14px] text-muted-foreground">
            <IconMonument className="h-3.5 w-3.5" style={{ color: C.blueLight }} />
            <span className="truncate">{monument.nom}</span>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {travaux.length > 0 ? (
              // Sans titre saisi, projetTitre() liste déjà ces travaux dans le
              // h1 : les redire en badges les affichait deux fois.
              titreExplicite &&
              travaux.map((t) => (
                <Badge
                  key={t}
                  variant="outline"
                  className="gap-1"
                  style={{ borderColor: C.border, color: C.orange, background: C.paleOrange }}
                >
                  <IconChantier className="h-3 w-3" />
                  {WORK_LABELS[t] ?? t}
                </Badge>
              ))
            ) : (
              // Liste vide = « Pas encore déterminé » : aucune aide n'est filtrée
              // sur le type de travaux, et il faut que ça se voie.
              <Badge variant="outline" style={{ borderColor: C.border, color: C.grayFg }}>
                Travaux pas encore déterminés
              </Badge>
            )}
            {projet.clotureAt && (
              <Badge variant="outline" style={{ borderColor: C.border, color: C.grayFg }}>
                Clôturé
              </Badge>
            )}
          </div>
        </div>

        {projectPermissions(projet.myRole ?? null).canAccessAides && (
          <button
            onClick={onRefaireQuestionnaire}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md shrink-0"
            style={{ background: C.orange }}
          >
            <IconRafraichir className="h-4 w-4" strokeWidth={2} />
            Refaire le questionnaire
          </button>
        )}
      </div>
    </div>
  );
}
