import { MonumentPhotoProfil } from '@/components/monument/MonumentPhotoProfil';
import { Picto } from '@/components/shared/ecrans/Picto';
import { SharedBadge } from '@/components/sharing/SharedBadge';
import { RoleBadge } from '@/components/sharing/RoleBadge';
import { isProjectShared, projectPermissions } from '@/lib/project-permissions';
import type { Monument, ProjectMember } from '@/types';

/** Libellé de la pastille de protection, à la manière de la maquette. */
const PROTECTION_PASTILLE: Record<string, string> = {
  classe: 'Classé monument historique',
  inscrit: 'Inscrit monument historique',
  abords: "Abords d'un monument historique",
  spr: 'Site patrimonial remarquable',
  non_protege: 'Non protégé',
};

/**
 * En-tête de la page monument (maquette `monumia-page-monument.html`) : la
 * photo à gauche (ou l'invite à en ajouter une), le nom, le lieu, la
 * protection, et le lien vers la fiche.
 */
export function EnTeteMonument({
  monument,
  members = [],
  onModifier,
}: {
  monument: Monument;
  members?: ProjectMember[];
  /** Absent sans le droit de modifier la fiche. */
  onModifier?: () => void;
}) {
  const lieu = [monument.commune, monument.departement].filter(Boolean).join(', ');
  const canEdit = projectPermissions(monument.myRole ?? null).canEditProject;
  const partage = isProjectShared({
    myRole: monument.myRole,
    memberCount: members.length || monument.memberCount,
  });
  const pastille = PROTECTION_PASTILLE[monument.protection];
  // La fiche est « à compléter » tant qu'elle n'est pas remplie ; ensuite on la
  // « modifie ». Le lien ne ment ni dans un sens ni dans l'autre.
  const lienFiche =
    monument.completionPercentage < 100 ? 'Compléter la fiche du monument' : 'Modifier la fiche du monument';

  return (
    <section className="head" aria-labelledby="mt">
      <MonumentPhotoProfil monument={monument} canEdit={canEdit} width={260} radius="16px" ratio={10 / 16} invite />
      <div className="id">
        <h1 id="mt">{monument.nom}</h1>
        {lieu && <p className="loc">{lieu}</p>}
        {(pastille || partage) && (
          <div className="tags">
            {pastille && <span className="tag">{pastille}</span>}
            {partage && <SharedBadge count={members.length || monument.memberCount} />}
            {partage && monument.myRole && <RoleBadge role={monument.myRole} />}
          </div>
        )}
        {onModifier && (
          <button className="edit" type="button" onClick={onModifier}>
            <Picto nom="crayon" />
            {lienFiche}
          </button>
        )}
      </div>
    </section>
  );
}
