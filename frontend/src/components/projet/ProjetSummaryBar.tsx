import { IconChantier, IconMonument, IconRafraichir } from '@/components/icons';
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
}: ProjetSummaryBarProps) {
  const travaux = projet.travauxEnvisages ?? [];
  const titreExplicite = !!projet.titre?.trim();

  return (
    <div
      className="rounded-2xl border p-6 sm:p-7"
      style={{ background: C.card, borderColor: C.border }}
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3 min-w-0">
          <h1 className="text-[clamp(1.5rem,3vw,2rem)] leading-tight" style={{ fontFamily: SERIF, color: C.ink }}>
            {projetTitre(projet)}
          </h1>
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
