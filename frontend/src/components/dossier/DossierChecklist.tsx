import { useEffect, useState } from 'react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Picto } from '@/components/shared/ecrans/Picto';
import { PictoDoc } from '@/components/document/PictosDocuments';
import { BarreSection } from '@/components/document/EspaceDocuments';
import { documentService } from '@/services/document.service';
import { templateService } from '@/services/template.service';
import { formatBadge } from '@/lib/template-format';
import { compterChecklist } from '@/lib/checklist-progress';
import type { ChecklistItem, Template } from '@/types';
import '@/components/document/documents.css';

/** Défense : un label malformé (dossier stocké avec un objet document
 *  {nom, …} au lieu d'une chaîne) ne doit pas faire planter le rendu React. */
function labelText(label: unknown): string {
  if (typeof label === 'string') return label;
  if (label && typeof label === 'object' && 'nom' in label) {
    return String((label as { nom: unknown }).nom ?? '');
  }
  return '';
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
  /** Le nom du document qui remplit la pièce, s'il est connu. */
  nomDocument?: (documentId: string) => string | undefined;
  /** « Déposer » : un nouveau fichier pour cette pièce. */
  onRequestDeposer?: (item: ChecklistItem) => void;
  /** « Choisir un document » / « Remplacer ». */
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
 * Les pièces d'un dossier, avec les emplacements de l'espace documents
 * (`.req` / `.slot`, cf. PiecesADeposer) : en pointillé tant qu'une pièce
 * manque, en vert une fois fournie, en bleu quand un fichier déjà envoyé a été
 * repris et attend d'être vérifié.
 */
export function DossierChecklist({
  items,
  projetId,
  templatesByItemId,
  documentUrlByItemId,
  libelle = (l) => l,
  nomDocument,
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
  const { confirmees, aVerifier, total } = compterChecklist(items);

  // Documents que l'utilisateur a le DROIT de voir (le backend filtre déjà selon
  // la visibilité). Une pièce dont le documentId n'y est pas est masquée pour lui
  // → cadenas au lieu de « Voir ».
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

  return (
    <section className="desp pdos-pieces" aria-label="Pièces du dossier">
      <BarreSection
        titre="Pièces du dossier"
        droite={total > 0 && (
          <div className="pdep-prog">
            <span>
              {confirmees} sur {total} confirmée{confirmees > 1 ? 's' : ''}
              {aVerifier > 0 && ` · ${aVerifier} à vérifier`}
            </span>
            <span className="track"><i style={{ width: `${(confirmees / total) * 100}%` }} /></span>
          </div>
        )}
      />

      {sorted.length === 0 ? (
        <div className="empty">
          <b>Aucune pièce</b>
          <p>Ce dossier ne comporte aucune pièce à fournir.</p>
        </div>
      ) : (
        <div className="req">
          {sorted.map((item) => (
            <SlotPiece
              key={item.id}
              item={item}
              nom={libelle(labelText(item.label))}
              nomDocument={item.documentId ? nomDocument?.(item.documentId) : undefined}
              templates={templatesByItemId?.[item.id] ?? []}
              documentUrl={documentUrlByItemId?.[item.id]}
              readOnly={readOnly}
              canModify={canModifyItem ? canModifyItem(item) : true}
              busy={busyItemId === item.id}
              hidden={!!item.documentId && viewableDocIds !== null && !viewableDocIds.has(item.documentId)}
              onRequestDeposer={onRequestDeposer}
              onRequestAttach={onRequestAttach}
              onPreview={onPreview}
              onRequestDelete={onRequestDelete}
              onConfirm={onConfirm}
              onReject={onReject}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function SlotPiece({
  item,
  nom,
  nomDocument,
  templates,
  documentUrl,
  readOnly,
  canModify,
  busy,
  hidden,
  onRequestDeposer,
  onRequestAttach,
  onPreview,
  onRequestDelete,
  onConfirm,
  onReject,
}: {
  item: ChecklistItem;
  nom: string;
  nomDocument?: string;
  templates: Template[];
  documentUrl?: string;
  readOnly?: boolean;
  canModify: boolean;
  busy: boolean;
  hidden: boolean;
} & Pick<
  DossierChecklistProps,
  'onRequestDeposer' | 'onRequestAttach' | 'onPreview' | 'onRequestDelete' | 'onConfirm' | 'onReject'
>) {
  const isFourni = item.statut === 'fourni';
  const isRepris = item.statut === 'repris';
  const classe = isFourni ? 'slot ok' : isRepris ? `slot rep${item.perime ? ' vieux' : ''}` : 'slot';
  const voir = (isFourni || isRepris) && item.documentId && !hidden && onPreview
    ? () => onPreview(item.documentId!)
    : undefined;

  return (
    <div className={classe}>
      <b>{nom}</b>
      <small>
        {isFourni && hidden ? (
          <><Picto nom="cadenas" />Fourni · accès réservé</>
        ) : isFourni ? (
          <><Picto nom="coche" />Fourni</>
        ) : isRepris ? (
          <><Picto nom="refaire" />{item.perime ? 'Repris, document ancien : à vérifier' : 'Repris d’un autre dossier : à vérifier'}</>
        ) : (
          <>{item.obligatoire ? 'Obligatoire' : 'Facultative'} · à fournir</>
        )}
      </small>
      {item.description && <p className="where">{item.description}</p>}
      {/* Le nom du fichier, s'il dit autre chose que la pièce (un dépôt depuis
          « Déposer » prend le nom de la pièce). */}
      {(isFourni || isRepris) && nomDocument && nomDocument !== nom && !hidden && (
        <p className="where">{isRepris ? 'Fichier proposé : ' : 'Fichier : '}{nomDocument}</p>
      )}

      <div className="pdos-acts">
        {/* Confirmer une pièce qu'on ne peut pas ouvrir serait confirmer à
            l'aveugle : le bouton disparaît avec « Voir ». Le rejet, lui, ne
            demande pas de consulter le document : il reste offert pour ne pas
            laisser la pièce dans une impasse. */}
        {!readOnly && isRepris && !hidden && onConfirm && (
          <button className="btn b-blue b-sm" type="button" disabled={busy} onClick={() => onConfirm(item)}>
            <Picto nom="coche" />C’est bien ça
          </button>
        )}
        {!readOnly && isRepris && onReject && (
          <button className="btn b-line b-sm" type="button" disabled={busy} onClick={() => onReject(item)}>
            Ce n’est pas ça
          </button>
        )}
        {!readOnly && !isFourni && !isRepris && onRequestDeposer && (
          <button className="btn b-blue b-sm" type="button" disabled={busy} onClick={() => onRequestDeposer(item)}>
            <Picto nom="envoyer" />{busy ? 'Envoi…' : 'Déposer'}
          </button>
        )}
        {voir && (
          isFourni ? (
            <button className="btn b-line b-sm" type="button" onClick={voir}>
              <PictoDoc nom="oeil" />Voir
            </button>
          ) : (
            <button className="lnk" type="button" onClick={voir}>Voir le fichier</button>
          )
        )}
        {!readOnly && !isFourni && !isRepris && onRequestAttach && (
          <button className="lnk" type="button" disabled={busy} onClick={() => onRequestAttach(item)}>
            Choisir un document
          </button>
        )}
        {!readOnly && isFourni && canModify && !hidden && onRequestAttach && (
          <button className="lnk" type="button" disabled={busy} onClick={() => onRequestAttach(item)}>
            Remplacer
          </button>
        )}
        {!readOnly && isFourni && item.documentId && canModify && !hidden && onRequestDelete && (
          <button className="lnk del" type="button" disabled={busy} onClick={() => onRequestDelete(item)}>
            Retirer
          </button>
        )}
        <BoutonModele templates={templates} />
        {documentUrl && (
          <a
            className="lnk"
            href={documentUrl}
            target="_blank"
            rel="noopener noreferrer"
            title="Le formulaire, Cerfa ou modèle officiel de la pièce"
          >
            <Picto nom="telecharger" />Formulaire officiel
          </a>
        )}
      </div>
    </div>
  );
}

// « Modèle » : présent quand au moins un modèle de la bibliothèque correspond à
// la pièce. Un seul modèle → téléchargement direct ; plusieurs → liste dans un
// popover. Aucun modèle → rien (cas fréquent, assumé).
function BoutonModele({ templates }: { templates: Template[] }) {
  if (templates.length === 0) return null;

  if (templates.length === 1) {
    const t = templates[0];
    return (
      <button className="lnk" type="button" onClick={() => templateService.download(t)} title={`Télécharger le modèle : ${t.nom}`}>
        <Picto nom="telecharger" />Modèle
      </button>
    );
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="lnk" type="button">
          <Picto nom="telecharger" />Modèles ({templates.length})
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="ec dmenu pdos-modeles">
        <p className="pdos-modeles-t">Modèles suggérés</p>
        {templates.map((t) => {
          const badge = formatBadge(t.extension);
          return (
            <button key={t.id} type="button" onClick={() => templateService.download(t)}>
              <span className={`fmt ${badge.className}`}>{badge.label}</span>
              <span className="nomlieu">{t.nom}</span>
            </button>
          );
        })}
      </PopoverContent>
    </Popover>
  );
}
