import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Picto } from '@/components/shared/ecrans/Picto';
import { BarreSection } from '@/components/document/EspaceDocuments';
import { usePiecesADeposer } from '@/hooks/usePiecesADeposer';
import { dossierLabel } from '@/lib/document-type-meta';
import type { PieceADeposer } from '@/lib/pieces-a-deposer';
import { projetTitre } from '@/lib/projet-titre';
import { useMonumentStore } from '@/stores/useMonumentStore';
import type { Document } from '@/types';
import './documents.css';

/** Au-delà, les pièces se replient derrière « Voir les N autres pièces ». */
const PIECES_VISIBLES = 6;

export interface PiecesADeposerProps {
  monumentId: string;
  /** Restreint aux aides de ces projets (par défaut : les projets ouverts). */
  projetIds?: string[];
  /** « Déposer » : ouvrir le dépôt pré-rempli pour cette pièce. */
  onDeposer: (piece: PieceADeposer) => void;
  /** Masquer « Déposer » (lecture seule : pas le droit de déposer ici). */
  lectureSeule?: boolean;
  /** Documents chargés à part par l'onglet, en plus de ceux du store. */
  documents?: Document[];
  /** Replier au-delà de six pièces (l'onglet d'un monument ou d'un projet, où
   *  la liste des documents suit). Faux sur la section dédiée de Mes documents. */
  replier?: boolean;
}

/**
 * « Demandées par les aides de votre projet » (maquette `.req` / `.slot`) : un
 * emplacement par pièce, en pointillé tant qu'elle manque, en vert une fois
 * déposée. Absente s'il n'y a aucun projet ou aucune pièce.
 */
export function PiecesADeposer({
  monumentId, projetIds, onDeposer, lectureSeule, documents, replier = true,
}: PiecesADeposerProps) {
  const { t } = useTranslation('documents');
  const { pieces, projets } = usePiecesADeposer(monumentId, projetIds, documents);
  const monumentNom = useMonumentStore((s) => s.monuments.find((m) => m.id === monumentId)?.nom);
  const [tout, setTout] = useState(false);

  if (projets.length === 0 || pieces.length === 0) return null;

  const deposees = pieces.filter((p) => p.deposee).length;
  const visibles = tout || !replier ? pieces : pieces.slice(0, PIECES_VISIBLES);
  const reste = pieces.length - visibles.length;
  const titre = projets.length === 1
    ? t('PiecesADeposer.titreUnProjet', { projet: projetTitre(projets[0], monumentNom) })
    : t('PiecesADeposer.titrePlusieurs');

  return (
    <section className="pdep" aria-label={t('PiecesADeposer.aria')}>
      <BarreSection
        titre={titre}
        droite={(
          <div className="pdep-prog">
            <span>{t('PiecesADeposer.deposees', { count: deposees, total: pieces.length })}</span>
            <span className="track"><i style={{ width: `${(deposees / pieces.length) * 100}%` }} /></span>
          </div>
        )}
      />

      <div className="req">
        {visibles.map((p) =>
          p.deposee ? (
            <div key={p.pieceId} className="slot ok">
              <b>{p.nom}</b>
              <small><Picto nom="coche" />{t('PiecesADeposer.deposeDossier', { dossier: dossierLabel(p.typeDocument) })}</small>
            </div>
          ) : (
            <div key={p.pieceId} className="slot">
              <b>{p.nom}</b>
              <small>
                {t('PiecesADeposer.demandeePar', { dossier: dossierLabel(p.typeDocument), count: p.nbAides })}
              </small>
              {p.description && <p className="where">{p.description}</p>}
              {!lectureSeule && (
                <button className="btn b-blue b-sm" type="button" onClick={() => onDeposer(p)}>
                  <Picto nom="envoyer" />{t('PiecesADeposer.deposer')}
                </button>
              )}
            </div>
          ),
        )}
      </div>

      {reste > 0 && (
        <button className="btn b-line b-sm pdep-plus" type="button" onClick={() => setTout(true)}>
          {t('PiecesADeposer.voirAutres', { count: reste })}
        </button>
      )}
    </section>
  );
}
