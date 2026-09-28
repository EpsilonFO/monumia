import { useState } from 'react';
import { Picto } from '@/components/shared/ecrans/Picto';
import { usePiecesADeposer } from '@/hooks/usePiecesADeposer';
import { typeLabel } from '@/lib/document-type-meta';
import type { PieceADeposer } from '@/lib/pieces-a-deposer';
import { projetTitre } from '@/lib/projet-titre';
import type { Document } from '@/types';
import './documents.css';

/** Au-delà, les pièces se replient derrière « Voir les N autres pièces ». */
const PIECES_VISIBLES = 6;

export interface PiecesADeposerProps {
  monumentId: string;
  /** Restreint aux aides de ces projets (par défaut : les projets ouverts). */
  projetIds?: string[];
  /** « Déposer » : ouvrir la fenêtre d'ajout pré-remplie pour cette pièce. */
  onDeposer: (piece: PieceADeposer) => void;
  /** Masquer « Déposer » (lecture seule : pas le droit de déposer ici). */
  lectureSeule?: boolean;
  /** Documents chargés à part par l'onglet, en plus de ceux du store. */
  documents?: Document[];
}

/**
 * « À déposer pour vos aides » (maquette `.need` / `.piece`) : une carte par
 * pièce, bordure orange tant qu'elle manque, verte une fois déposée, avec la
 * jauge « N sur M ». Absente s'il n'y a aucun projet ou aucune pièce.
 */
export function PiecesADeposer({ monumentId, projetIds, onDeposer, lectureSeule, documents }: PiecesADeposerProps) {
  const { pieces, projets } = usePiecesADeposer(monumentId, projetIds, documents);
  const [tout, setTout] = useState(false);

  if (projets.length === 0 || pieces.length === 0) return null;

  const deposees = pieces.filter((p) => p.deposee).length;
  const visibles = tout ? pieces : pieces.slice(0, PIECES_VISIBLES);
  const reste = pieces.length - visibles.length;
  const sousTitre = projets.length === 1
    ? `Les pièces que demandent les aides de votre projet ${projetTitre(projets[0])}.`
    : 'Les pièces que demandent les aides de vos projets sur ce monument.';

  return (
    <section className="pdep" aria-labelledby="pdep-titre">
      <div className="sec-h">
        <div>
          <h2 id="pdep-titre">À déposer pour vos aides</h2>
          <p>{sousTitre}</p>
        </div>
        <div className="pdep-prog">
          <span>{deposees} sur {pieces.length}</span>
          <span className="track"><i style={{ width: `${(deposees / pieces.length) * 100}%` }} /></span>
        </div>
      </div>

      <div className="pdep-need">
        {visibles.map((p) =>
          p.deposee ? (
            <div key={p.pieceId} className="pdep-piece done">
              <div className="hd">
                <div>
                  <b>{p.nom}</b>
                  <div className="ty">{typeLabel(p.typeDocument)}</div>
                </div>
                <span className="ok"><Picto nom="coche" />Déposé</span>
              </div>
            </div>
          ) : (
            <div key={p.pieceId} className="pdep-piece">
              <div className="hd">
                <div>
                  <b>{p.nom}</b>
                  <div className="ty">Type : {typeLabel(p.typeDocument)}</div>
                </div>
              </div>
              <span className="for">Demandé par {p.nbAides} de vos aides</span>
              {p.description && <p className="where">{p.description}</p>}
              {!lectureSeule && (
                <button className="btn b-blue b-sm" type="button" onClick={() => onDeposer(p)}>
                  <Picto nom="envoyer" />Déposer
                </button>
              )}
            </div>
          ),
        )}
      </div>

      {reste > 0 && (
        <button className="btn b-line b-sm pdep-plus" type="button" onClick={() => setTout(true)}>
          {reste === 1 ? "Voir l'autre pièce" : `Voir les ${reste} autres pièces`}
        </button>
      )}
    </section>
  );
}
