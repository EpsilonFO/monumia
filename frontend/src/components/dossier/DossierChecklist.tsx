import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import { Picto } from '@/components/shared/ecrans/Picto';
import { documentService } from '@/services/document.service';
import { templateService } from '@/services/template.service';
import type { ChecklistItem, Template } from '@/types';

/** Défense : un label malformé (dossier stocké avec un objet document
 *  {nom, …} au lieu d'une chaîne) ne doit pas faire planter le rendu React. */
function labelText(label: unknown): string {
  if (typeof label === 'string') return label;
  if (label && typeof label === 'object' && 'nom' in label) {
    return String((label as { nom: unknown }).nom ?? '');
  }
  return '';
}

/** Ce que la tuile montre du fichier qui remplit une pièce. */
export interface FichierPiece {
  nom: string;
  /** PDF, JPG… */
  ext: string;
  image: boolean;
}

interface DossierChecklistProps {
  items: ChecklistItem[];
  /** Projet du dossier : c'est sa liste de documents qui dit ce que l'on peut ouvrir. */
  projetId: string;
  /** Modèles de la bibliothèque correspondant à chaque pièce (par id de pièce). */
  templatesByItemId?: Record<string, Template[]>;
  /** Lien de téléchargement officiel de la pièce (Cerfa / formulaire), par id de pièce. */
  documentUrlByItemId?: Record<string, string>;
  /** Le libellé affiché d'une pièce (celui de la fiche rédigée de l'aide, s'il existe). */
  libelle?: (label: string) => string;
  /** Le fichier qui remplit la pièce, s'il est connu. */
  fichierDe?: (documentId: string) => FichierPiece | undefined;
  /** « Importer depuis l'ordinateur » : un nouveau fichier pour cette pièce. */
  onRequestDeposer?: (item: ChecklistItem) => void;
  /** « Choisir dans Mes documents » / « Remplacer ». */
  onRequestAttach?: (item: ChecklistItem) => void;
  onPreview?: (documentId: string) => void;
  onRequestDelete?: (item: ChecklistItem) => void;
  /** Confirme une pièce reprise (« c'est bien ce document »). */
  onConfirm?: (item: ChecklistItem) => void;
  /** Rejette une pièce reprise (mauvais document). */
  onReject?: (item: ChecklistItem) => void;
  /** Vrai si l'utilisateur peut remplacer/supprimer la pièce (= il en est l'auteur). */
  canModifyItem?: (item: ChecklistItem) => boolean;
  busyItemId?: string | null;
  readOnly?: boolean;
}

/**
 * Les pièces d'un dossier en grille de tuiles (maquette `monumia-dossier.html`) :
 * cercle vide et « Ajouter » tant qu'une pièce manque, en vert avec son fichier
 * une fois fournie, en bleu quand un fichier déjà envoyé a été repris et attend
 * d'être vérifié.
 */
export function DossierChecklist({
  items,
  projetId,
  templatesByItemId,
  documentUrlByItemId,
  libelle = (l) => l,
  fichierDe,
  onRequestDeposer,
  onRequestAttach,
  onPreview,
  onRequestDelete,
  onConfirm,
  onReject,
  canModifyItem,
  busyItemId,
  readOnly,
}: DossierChecklistProps) {
  const sorted = [...items].sort((a, b) => a.ordre - b.ordre);

  // Un seul menu « Ajouter » ouvert à la fois.
  const [menuOuvert, setMenuOuvert] = useState<string | null>(null);

  // La tuile qui vient d'être remplie s'illumine un instant.
  const [fraiche, setFraiche] = useState<string | null>(null);
  const fournies = useRef<Set<string> | null>(null);
  const cleFournies = items.filter((i) => i.statut === 'fourni').map((i) => i.id).sort().join(',');
  useEffect(() => {
    const maintenant = new Set(cleFournies ? cleFournies.split(',') : []);
    const avant = fournies.current;
    fournies.current = maintenant;
    if (!avant) return;
    const nouvelle = [...maintenant].find((id) => !avant.has(id));
    if (!nouvelle) return;
    setFraiche(nouvelle);
    window.setTimeout(() => setFraiche((f) => (f === nouvelle ? null : f)), 1400);
  }, [cleFournies]);

  // Documents que l'utilisateur a le DROIT de voir (le backend filtre déjà selon
  // la visibilité). Une pièce dont le documentId n'y est pas est masquée pour lui
  // → cadenas au lieu du fichier.
  const [viewableDocIds, setViewableDocIds] = useState<Set<string> | null>(null);

  // Re-fetch quand l'ensemble des pièces fournies change (dépôt/remplacement) :
  // sans ça, un document fraîchement déposé n'est pas dans l'ensemble « visibles »
  // et s'affiche à tort comme « Réservé » jusqu'au rechargement de la page.
  const fourniKey = items
    .filter((i) => i.documentId)
    .map((i) => i.documentId)
    .sort()
    .join(',');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let visibles: Set<string>;
      try {
        const docs = await documentService.getAll({ projetId });
        visibles = new Set(docs.map((d) => d.id));
      } catch {
        if (!cancelled) setViewableDocIds(null);
        return;
      }
      // Une pièce reprise vient par construction d'un AUTRE projet (ou d'aucun) :
      // son document n'est jamais dans la liste du projet, et conclure « accès
      // réservé » afficherait un cadenas sur mon propre RIB. On interroge donc le
      // backend document par document — `getById` applique la même règle de
      // visibilité (`_require_document_view`), aucun chemin d'accès parallèle.
      const absents = [...new Set(fourniKey ? fourniKey.split(',') : [])]
        .filter((id) => id && !visibles.has(id));
      const resolus = await Promise.all(
        absents.map((id) => documentService.getById(id).then(() => id).catch(() => null)),
      );
      if (cancelled) return;
      for (const id of resolus) if (id) visibles.add(id);
      setViewableDocIds(visibles);
    })();
    return () => { cancelled = true; };
  }, [projetId, fourniKey]);

  if (sorted.length === 0) {
    return (
      <div className="pvide">
        <b>Aucune pièce</b>
        <p>Ce dossier ne comporte aucune pièce à fournir.</p>
      </div>
    );
  }

  return (
    <div className="pgrid">
      {sorted.map((item) => (
        <TuilePiece
          key={item.id}
          item={item}
          nom={libelle(labelText(item.label))}
          fichier={item.documentId ? fichierDe?.(item.documentId) : undefined}
          templates={templatesByItemId?.[item.id] ?? []}
          documentUrl={documentUrlByItemId?.[item.id]}
          readOnly={readOnly}
          canModify={canModifyItem ? canModifyItem(item) : true}
          busy={busyItemId === item.id}
          hidden={!!item.documentId && viewableDocIds !== null && !viewableDocIds.has(item.documentId)}
          fraiche={fraiche === item.id}
          menuOuvert={menuOuvert === item.id}
          setMenuOuvert={setMenuOuvert}
          onRequestDeposer={onRequestDeposer}
          onRequestAttach={onRequestAttach}
          onPreview={onPreview}
          onRequestDelete={onRequestDelete}
          onConfirm={onConfirm}
          onReject={onReject}
        />
      ))}
    </div>
  );
}

function TuilePiece({
  item,
  nom,
  fichier,
  templates,
  documentUrl,
  readOnly,
  canModify,
  busy,
  hidden,
  fraiche,
  menuOuvert,
  setMenuOuvert,
  onRequestDeposer,
  onRequestAttach,
  onPreview,
  onRequestDelete,
  onConfirm,
  onReject,
}: {
  item: ChecklistItem;
  nom: string;
  fichier?: FichierPiece;
  templates: Template[];
  documentUrl?: string;
  readOnly?: boolean;
  canModify: boolean;
  busy: boolean;
  hidden: boolean;
  fraiche: boolean;
  menuOuvert: boolean;
  setMenuOuvert: Dispatch<SetStateAction<string | null>>;
} & Pick<
  DossierChecklistProps,
  'onRequestDeposer' | 'onRequestAttach' | 'onPreview' | 'onRequestDelete' | 'onConfirm' | 'onReject'
>) {
  const isFourni = item.statut === 'fourni';
  const isRepris = item.statut === 'repris';
  const classe = [
    'tile',
    isFourni && 'done',
    isRepris && 'rep',
    isRepris && item.perime && 'vieux',
    fraiche && 'new',
  ].filter(Boolean).join(' ');
  const voir = (isFourni || isRepris) && item.documentId && !hidden && onPreview
    ? () => onPreview(item.documentId!)
    : undefined;

  const basculerMenu = useCallback(
    (ouvert: boolean) => setMenuOuvert(ouvert ? item.id : null),
    [item.id, setMenuOuvert],
  );
  const menuRef = useRef<HTMLDivElement>(null);
  const ajouterRef = useRef<HTMLButtonElement>(null);
  const menuId = `pmenu-${item.id}`;

  // Le menu se referme au clic dehors et à Échap (le focus revient alors sur
  // « Ajouter ») ; à l'ouverture, il passe sur la première entrée.
  useEffect(() => {
    if (!menuOuvert) return;
    menuRef.current?.querySelector<HTMLElement>('button, a')?.focus();
    const dehors = (e: PointerEvent) => {
      const cible = e.target as Node;
      if (menuRef.current?.contains(cible) || ajouterRef.current?.contains(cible)) return;
      basculerMenu(false);
    };
    const echap = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      basculerMenu(false);
      ajouterRef.current?.focus();
    };
    document.addEventListener('pointerdown', dehors);
    document.addEventListener('keydown', echap);
    return () => {
      document.removeEventListener('pointerdown', dehors);
      document.removeEventListener('keydown', echap);
    };
  }, [menuOuvert, basculerMenu]);

  const choisir = (action: () => void) => () => {
    basculerMenu(false);
    action();
  };

  const nomFichier = fichier?.nom ?? 'Fichier joint';

  return (
    <article className={classe}>
      <div className="t-top">
        <span className="st" aria-hidden="true">
          {isRepris ? <Picto nom="refaire" /> : <Picto nom="coche" />}
        </span>
        {item.obligatoire
          ? <span className="tag o">Obligatoire</span>
          : <span className="tag b">Selon votre situation</span>}
      </div>
      <b>{nom}</b>
      <span className="sr">
        {isFourni ? 'Pièce fournie.' : isRepris ? 'Pièce reprise, à vérifier.' : 'Pièce à fournir.'}
      </span>
      {item.description && <p className="how">{item.description}</p>}

      {(isFourni || isRepris) && hidden && (
        <span className="fchip off"><Picto nom="cadenas" /><span>Fourni · accès réservé</span></span>
      )}

      {(isFourni || isRepris) && !hidden && (
        <>
          {isRepris && (
            <small className="rep-t">
              {item.perime ? 'Document ancien, repris d’un autre dossier : à vérifier' : 'Repris d’un autre dossier : à vérifier'}
            </small>
          )}
          {voir ? (
            <button className="fchip" type="button" onClick={voir} title="Voir le fichier">
              {fichier && <span className={`ext${fichier.image ? ' img' : ''}`}>{fichier.ext}</span>}
              <span>{nomFichier}</span>
            </button>
          ) : (
            <span className="fchip">
              {fichier && <span className={`ext${fichier.image ? ' img' : ''}`}>{fichier.ext}</span>}
              <span>{nomFichier}</span>
            </span>
          )}
        </>
      )}

      {/* Confirmer une pièce qu'on ne peut pas ouvrir serait confirmer à
          l'aveugle : le bouton disparaît avec le fichier. Le rejet, lui, ne
          demande pas de consulter le document : il reste offert pour ne pas
          laisser la pièce dans une impasse. */}
      {!readOnly && isRepris && (
        <div className="t-acts">
          {!hidden && onConfirm && (
            <button className="btn b-blue add" type="button" disabled={busy} onClick={() => onConfirm(item)}>
              <Picto nom="coche" />C’est bien ça
            </button>
          )}
          {onReject && (
            <button className="rm" type="button" disabled={busy} onClick={() => onReject(item)}>
              Ce n’est pas ça
            </button>
          )}
        </div>
      )}

      {!readOnly && isFourni && item.documentId && canModify && !hidden && (onRequestDelete || onRequestAttach) && (
        <div className="t-acts">
          {onRequestDelete && (
            <button className="rm" type="button" disabled={busy} onClick={() => onRequestDelete(item)}>
              Retirer
            </button>
          )}
          {onRequestAttach && (
            <button className="rm" type="button" disabled={busy} onClick={() => onRequestAttach(item)}>
              Remplacer
            </button>
          )}
        </div>
      )}

      {!isFourni && !isRepris && (
        readOnly ? (
          <small className="manque">Non fournie</small>
        ) : (
          <>
            <button
              ref={ajouterRef}
              className="btn b-blue add"
              type="button"
              disabled={busy}
              aria-expanded={menuOuvert}
              aria-controls={menuOuvert ? menuId : undefined}
              onClick={() => basculerMenu(!menuOuvert)}
            >
              <Picto nom="plus" />{busy ? 'Ajout…' : 'Ajouter'}
            </button>
            {menuOuvert && (
              <div className="pmenu" id={menuId} ref={menuRef}>
                {documentUrl && (
                  <a
                    href={documentUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() => basculerMenu(false)}
                    title="Le formulaire, Cerfa ou modèle officiel de la pièce"
                  >
                    <Picto nom="telecharger" />Télécharger le modèle à remplir
                  </a>
                )}
                {templates.map((t) => (
                  <button key={t.id} type="button" onClick={choisir(() => templateService.download(t))}>
                    <Picto nom="telecharger" />
                    <span>
                      {templates.length === 1 && !documentUrl ? 'Télécharger le modèle à remplir' : `Modèle : ${t.nom}`}
                    </span>
                  </button>
                ))}
                {onRequestAttach && (
                  <button type="button" onClick={choisir(() => onRequestAttach(item))}>
                    <Picto nom="dossier" />Choisir dans Mes documents
                  </button>
                )}
                {onRequestDeposer && (
                  <button type="button" onClick={choisir(() => onRequestDeposer(item))}>
                    <Picto nom="envoyer" />Importer depuis l'ordinateur
                  </button>
                )}
              </div>
            )}
          </>
        )
      )}
    </article>
  );
}
