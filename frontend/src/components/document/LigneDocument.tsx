import { useState } from 'react';
import { toast } from 'sonner';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Picto, PictoPoints } from '@/components/shared/ecrans/Picto';
import { formatShortDate } from '@/lib/format-utils';
import { formatFichier, tailleFichier } from '@/lib/document-fichier';
import { downloadDocument } from '@/lib/document-download';
import { typeLabel } from '@/lib/document-type-meta';
import { VISIBILITY_META } from '@/lib/document-visibility';
import type { ActionDocument } from '@/lib/actions-document';
import type { Document } from '@/types';
import './documents.css';

export type { ActionDocument } from '@/lib/actions-document';

export interface LigneDocumentProps {
  document: Document;
  onVoir: () => void;
  /** Le menu ⋮ : renommer, changer le type, rattacher, gérer l'accès, corbeille… */
  actions: ActionDocument[];
  /** « Sert à N aides » : posé quand le document incarne une pièce que les aides
   *  du périmètre demandent (cf. lib/pieces-a-deposer). */
  nbAides?: number;
  /** Les chantiers auxquels il pend, en pastilles bleues. */
  rattachements?: string[];
  /** Nom de qui l'a déposé, quand ce n'est pas l'utilisateur courant. */
  auteur?: string;
  variant?: 'normal' | 'trash';
  /** Vient d'être déposé : un bref fond vert, comme dans la maquette. */
  nouveau?: boolean;
}

/**
 * Une ligne de la liste « Vos documents » (maquette `.doc`) : vignette de
 * format, nom en serif, « Type · taille · date », pastilles, puis « Voir »,
 * télécharger et le menu ⋮. Réutilisée par les onglets Documents des pages
 * monument et projet.
 */
export function LigneDocument({
  document: d, onVoir, actions, nbAides, rattachements = [], auteur, variant = 'normal', nouveau,
}: LigneDocumentProps) {
  const [telechargement, setTelechargement] = useState(false);
  const date = d.dateDocument ?? d.dateUpload;
  const restreint = variant === 'normal' && d.visibility !== 'team';
  const meta = [typeLabel(d.type), tailleFichier(d.tailleFichier), date ? formatShortDate(date) : null]
    .filter(Boolean)
    .join(' · ');

  const telecharger = async () => {
    setTelechargement(true);
    try {
      await downloadDocument(d);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Téléchargement impossible');
    } finally {
      setTelechargement(false);
    }
  };

  const normales = actions.filter((a) => !a.destructive);
  const destructives = actions.filter((a) => a.destructive);

  return (
    <article className={`ldoc${nouveau ? ' new' : ''}${variant === 'trash' ? ' trash' : ''}`}>
      <span className="dft" aria-hidden="true">{formatFichier(d.nomFichier)}</span>
      <div>
        <b title={d.nom}>{d.nom}</b>
        <p className="meta">
          {meta}
          {auteur && <> · déposé par {auteur}</>}
        </p>
        <div className="use">
          {rattachements.map((r) => (
            <span key={r} className="dpill t">{r}</span>
          ))}
          {restreint && (
            <span className="dpill t" title={VISIBILITY_META[d.visibility].help}>
              <Picto nom="cadenas" />Accès restreint
            </span>
          )}
          {variant === 'normal' && nbAides ? (
            <span className="dpill g">Sert à {nbAides} aide{nbAides > 1 ? 's' : ''}</span>
          ) : null}
        </div>
      </div>
      <div className="acts">
        <button className="btn b-blue b-sm" type="button" onClick={onVoir}>Voir</button>
        {variant === 'normal' && (
          <button
            className="ico"
            type="button"
            aria-label="Télécharger"
            title="Télécharger"
            onClick={telecharger}
            disabled={telechargement}
          >
            <Picto nom="telecharger" />
          </button>
        )}
        {actions.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="ico" type="button" aria-label="Plus d'actions" title="Plus d'actions">
                <PictoPoints />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {normales.map((a) => (
                <DropdownMenuItem key={a.label} onClick={a.onClick}>{a.label}</DropdownMenuItem>
              ))}
              {normales.length > 0 && destructives.length > 0 && <DropdownMenuSeparator />}
              {destructives.map((a) => (
                <DropdownMenuItem key={a.label} className="text-destructive" onClick={a.onClick}>
                  {a.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </article>
  );
}
