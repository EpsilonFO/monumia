import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { MonumentPhotoProfil } from '@/components/monument/MonumentPhotoProfil';
import { Picto } from '@/components/shared/ecrans/Picto';
import { SharedBadge } from '@/components/sharing/SharedBadge';
import { RoleBadge } from '@/components/sharing/RoleBadge';
import { isProjectShared, projectPermissions } from '@/lib/project-permissions';
import type { Monument, ProjectMember } from '@/types';

/** Libellé de la pastille de protection, à la manière de la maquette : la clé
 *  de `EnTeteMonument.pastille` qui sert chaque niveau. */
const PASTILLE_PROTECTION = {
  classe: 'classe',
  inscrit: 'inscrit',
  abords: 'abords',
  spr: 'spr',
  non_protege: 'nonProtege',
} as const;

/**
 * En-tête de la page monument (maquette `monumia-page-monument.html`) : la
 * photo à gauche (ou l'invite à en ajouter une), le nom, le lieu, la
 * protection, et le lien vers la fiche. Le nom se renomme en place, au crayon,
 * comme celui d'un projet (`ProjetSummaryBar`).
 */
export function EnTeteMonument({
  monument,
  members = [],
  onModifier,
  onRenommer,
}: {
  monument: Monument;
  members?: ProjectMember[];
  /** Absent sans le droit de modifier la fiche. */
  onModifier?: () => void;
  /** Renomme le monument. Absent sans le droit de modifier la fiche. Doit lever
   *  si l'enregistrement échoue : le champ reste ouvert, la saisie n'est pas perdue. */
  onRenommer?: (nom: string) => Promise<void>;
}) {
  const { t } = useTranslation('monuments');
  const lieu = [monument.commune, monument.departement].filter(Boolean).join(', ');
  const canEdit = projectPermissions(monument.myRole ?? null).canEditProject;
  const partage = isProjectShared({
    myRole: monument.myRole,
    memberCount: members.length || monument.memberCount,
  });
  const clePastille = Object.hasOwn(PASTILLE_PROTECTION, monument.protection)
    ? PASTILLE_PROTECTION[monument.protection as keyof typeof PASTILLE_PROTECTION]
    : undefined;
  const pastille = clePastille ? t(`EnTeteMonument.pastille.${clePastille}`) : undefined;
  // La fiche est « à compléter » tant qu'elle n'est pas remplie ; ensuite on la
  // « modifie ». Le lien ne ment ni dans un sens ni dans l'autre.
  const lienFiche =
    monument.completionPercentage < 100
      ? t('EnTeteMonument.completerFiche')
      : t('EnTeteMonument.modifierFiche');

  const [edition, setEdition] = useState(false);
  const [saisie, setSaisie] = useState(monument.nom);
  const [enregistrement, setEnregistrement] = useState(false);
  const champRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (edition) champRef.current?.select();
  }, [edition]);

  function ouvrirEdition() {
    setSaisie(monument.nom);
    setEdition(true);
  }

  async function valider() {
    const nom = saisie.trim();
    // Au moins un caractère : un nom vide ne remplace jamais celui en place.
    if (!nom || !onRenommer) return;
    if (nom === monument.nom) {
      setEdition(false);
      return;
    }
    setEnregistrement(true);
    try {
      await onRenommer(nom);
      setEdition(false);
    } catch {
      // L'erreur est signalée par l'appelant : on reste en édition.
    } finally {
      setEnregistrement(false);
    }
  }

  return (
    <section className="head" aria-labelledby="mt">
      <MonumentPhotoProfil monument={monument} canEdit={canEdit} width={295} radius="18px" ratio={10 / 16} invite />
      <div className="id">
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
              // on revient alors au nom en place plutôt que de bloquer.
              onBlur={() => (saisie.trim() ? void valider() : setEdition(false))}
              disabled={enregistrement}
              aria-label={t('EnTeteMonument.nomAria')}
              autoFocus
              className={saisie.trim() ? 'renommer' : 'renommer vide'}
            />
            <p className="aide-saisie">
              {saisie.trim()
                ? t('EnTeteMonument.aideValider')
                : t('EnTeteMonument.nomVide')}
            </p>
          </>
        ) : (
          <h1 id="mt">
            {monument.nom}
            {onRenommer && (
              <button
                className="crayon"
                type="button"
                onClick={ouvrirEdition}
                aria-label={t('EnTeteMonument.renommer')}
                title={t('EnTeteMonument.renommer')}
              >
                <Picto nom="crayon" />
              </button>
            )}
          </h1>
        )}
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
