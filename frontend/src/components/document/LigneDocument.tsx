import { useState, type ReactNode } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Picto, PictoPoints, type NomPicto } from '@/components/shared/ecrans/Picto';
import { PictoDoc, type NomPictoDoc } from '@/components/document/PictosDocuments';
import { useDocumentThumbnail } from '@/components/document/useDocumentThumbnail';
import { formatShortDate } from '@/lib/format-utils';
import { formatFichier, tailleFichier } from '@/lib/document-fichier';
import { downloadDocument } from '@/lib/document-download';
import { dossierLabel } from '@/lib/document-type-meta';
import { VISIBILITY_META } from '@/lib/document-visibility';
import { estImage } from '@/lib/documents-espace';
import type { ActionDocument, CleActionDocument } from '@/lib/actions-document';
import type { Document } from '@/types';
import './documents.css';

export type { ActionDocument } from '@/lib/actions-document';

export interface DocumentAfficheProps {
  document: Document;
  onVoir: () => void;
  /** Le menu ⋮ après « Aperçu » et « Télécharger » : renommer, changer de
   *  dossier, rattacher, gérer l'accès, corbeille… (cf. lib/actions-document). */
  actions: ActionDocument[];
  /** « Sert à N aides » : posé quand le document incarne une pièce que les aides
   *  du périmètre demandent (cf. lib/pieces-a-deposer). */
  nbAides?: number;
  /** Les chantiers ou dossiers auxquels il pend, en pastilles bleues. */
  rattachements?: string[];
  /** Nom de qui l'a déposé, quand ce n'est pas l'utilisateur courant. */
  auteur?: string;
  variant?: 'normal' | 'trash';
  /** Vient d'être déposé : un bref liseré vert, comme dans la maquette. */
  nouveau?: boolean;
  selectionne?: boolean;
  /** Absent : pas de case à cocher (la corbeille). */
  onSelection?: () => void;
}

const PICTO_ACTION: Record<CleActionDocument, { doc?: NomPictoDoc; ecran?: NomPicto }> = {
  renommer: { ecran: 'crayon' },
  deplacer: { doc: 'deplacer' },
  rattacher: { doc: 'rattacher' },
  acces: { ecran: 'cadenas' },
  corbeille: { doc: 'corbeille' },
  retirer: { ecran: 'croix' },
  restaurer: { doc: 'restaurer' },
  supprimer: { doc: 'corbeille' },
};

function PictoAction({ cle }: { cle?: CleActionDocument }) {
  if (!cle) return null;
  const p = PICTO_ACTION[cle];
  return p.doc ? <PictoDoc nom={p.doc} /> : p.ecran ? <Picto nom={p.ecran} /> : null;
}

/**
 * Le menu ⋮ d'un document (maquette `.menu`) : Aperçu et Télécharger pour qui
 * le voit, puis les gestes que ses droits ouvrent, le destructif à la fin.
 */
function MenuDocument({ document: d, onVoir, actions, variant = 'normal' }: Pick<DocumentAfficheProps, 'document' | 'onVoir' | 'actions' | 'variant'>) {
  const { t } = useTranslation(['documents', 'common']);
  const [telechargement, setTelechargement] = useState(false);
  const telecharger = async () => {
    setTelechargement(true);
    try {
      await downloadDocument(d);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('commun.telechargementImpossible'));
    } finally {
      setTelechargement(false);
    }
  };
  const normales = actions.filter((a) => !a.destructive);
  const destructives = actions.filter((a) => a.destructive);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="kebab" type="button" aria-label={t('LigneDocument.actionsPour', { nom: d.nom })} title={t('commun.plusActions')}>
          <PictoPoints />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="ec dmenu">
        <DropdownMenuItem onClick={onVoir}><PictoDoc nom="oeil" />{t('LigneDocument.apercu')}</DropdownMenuItem>
        {variant === 'normal' && (
          <DropdownMenuItem onClick={telecharger} disabled={telechargement}>
            <Picto nom="telecharger" />{t('common:actions.telecharger')}
          </DropdownMenuItem>
        )}
        {normales.map((a) => (
          <DropdownMenuItem key={a.label} onClick={a.onClick}><PictoAction cle={a.cle} />{a.label}</DropdownMenuItem>
        ))}
        {destructives.length > 0 && <DropdownMenuSeparator />}
        {destructives.map((a) => (
          <DropdownMenuItem key={a.label} className="del" onClick={a.onClick}>
            <PictoAction cle={a.cle} />{a.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Les pastilles sous le nom : chantiers, accès restreint, « Sert à N aides », auteur. */
function Pastilles({ document: d, nbAides, rattachements = [], auteur, variant = 'normal' }: DocumentAfficheProps): ReactNode {
  const { t } = useTranslation(['documents', 'common']);
  const restreint = variant === 'normal' && d.visibility !== 'team';
  const aides = variant === 'normal' && !!nbAides;
  if (!rattachements.length && !restreint && !aides && !auteur) return null;
  return (
    <span className="use">
      {rattachements.map((r) => <span key={r} className="dpill t">{r}</span>)}
      {restreint && (
        <span className="dpill t" title={VISIBILITY_META[d.visibility].help}>
          <Picto nom="cadenas" />{t('commun.accesRestreint')}
        </span>
      )}
      {aides && <span className="dpill g">{t('LigneDocument.serta', { count: nbAides ?? 0 })}</span>}
      {auteur && <span className="par">{t('LigneDocument.deposePar', { auteur })}</span>}
    </span>
  );
}

function PastilleFormat({ document: d }: { document: Document }) {
  const format = formatFichier(d.nomFichier);
  return <span className={`ext${estImage(format, d.mimeType) ? ' img' : ''}`}>{format}</span>;
}

/**
 * Une carte de la grille (maquette `.file`) : l'aperçu (la vraie première page
 * pour une image ou un PDF, une feuille stylisée sinon), le format, le nom,
 * « Dossier · date » et le menu ⋮. Cliquer l'aperçu ouvre le document.
 */
export function CarteDocument(props: DocumentAfficheProps) {
  const { t } = useTranslation(['documents', 'common']);
  const { document: d, onVoir, variant = 'normal', nouveau, selectionne, onSelection } = props;
  const { ref, preview } = useDocumentThumbnail(d.id, d.mimeType, d.nomFichier, { texte: false });
  const date = d.dateDocument ?? d.dateUpload;
  const image = preview?.kind === 'image' ? preview : null;

  return (
    <div className={`file${selectionne ? ' sel' : ''}${nouveau ? ' new' : ''}${variant === 'trash' ? ' trash' : ''}`}>
      {onSelection && (
        <button
          type="button"
          className="ck"
          aria-pressed={!!selectionne}
          aria-label={t('LigneDocument.selectionner', { nom: d.nom })}
          onClick={onSelection}
        >
          <Picto nom="coche" />
        </button>
      )}
      <button
        ref={ref as React.RefObject<HTMLButtonElement>}
        type="button"
        className="thumb"
        aria-label={t('LigneDocument.apercuDe', { nom: d.nom })}
        onClick={onVoir}
      >
        {image ? (
          <img src={image.url} alt="" className={image.fit === 'top' ? 'top' : undefined} loading="lazy" />
        ) : (
          <span className="sheet" aria-hidden="true"><i /><i /><i /><i /><i /><i /></span>
        )}
        <PastilleFormat document={d} />
      </button>
      <div className="meta">
        <div>
          <b title={d.nom}>{d.nom}</b>
          <small>{dossierLabel(d.type)}{date ? ` · ${formatShortDate(date)}` : ''}</small>
          <Pastilles {...props} />
        </div>
        <MenuDocument {...props} />
      </div>
    </div>
  );
}

/**
 * Une ligne du tableau (maquette `.table`) : nom, dossier, date d'ajout,
 * taille, menu ⋮. Le nom ouvre le document.
 */
export function LigneDocument(props: DocumentAfficheProps) {
  const { document: d, onVoir, selectionne, nouveau } = props;
  return (
    <tr className={`${selectionne ? 'sel' : ''}${nouveau ? ' new' : ''}`}>
      <td>
        <span className="nm">
          <PastilleFormat document={d} />
          <button type="button" onClick={onVoir} title={d.nom}>{d.nom}</button>
        </span>
        <Pastilles {...props} />
      </td>
      <td>{dossierLabel(d.type)}</td>
      <td>{d.dateUpload ? formatShortDate(d.dateUpload) : ''}</td>
      <td className="num">{tailleFichier(d.tailleFichier)}</td>
      <td><MenuDocument {...props} /></td>
    </tr>
  );
}
